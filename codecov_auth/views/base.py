import logging
import re
import uuid
from json import dumps
from urllib.parse import parse_qs, urlencode, urlparse

from django.conf import settings
from django.contrib.auth import login
from django.core.exceptions import SuspiciousOperation
from django.utils import timezone

from codecov_auth.helpers import create_signed_value
from codecov_auth.models import Owner, Session
from services.redis_configuration import get_redis_connection
from services.refresh import RefreshService
from services.segment import SegmentService
from utils.config import get_config
from utils.encryption import encryptor
from utils.services import get_short_service_name

log = logging.getLogger(__name__)


class StateMixin(object):
    """
    Implement the bevavior described here: https://auth0.com/docs/protocols/state-parameters

    - Generating a random string (called state) and storing it in Redis
    - Passing that state as argument to the oauth2 provider (eg github)
    - The oauth2 provider redirects to Codecov with the same state
    - We can verify if this state is in Redis, meaning Codecov generated when starting the redirection
    - Additionnally; we store in redis the redirection url after auth passed by the front-end
    - On the request callback; we can fetch the redirection url via the state
    - If the state is not in Redis; we raise an exception which will return a 400 error
    - Right before returning the response; we need to remove the state from Redis so it cannot be used again

    How to use:

    Mixin for a Django ClassBaseView (must have self.request set)

    To generate the state:
    - self.generate_state()
      -> Will return a state to give to the oauth2 provider.
      -> Will also store the redirect url from request.GET['to'] query param.

    To get the redirect url from state:
    - self.get_redirection_url_from_state(state)
      -> Will return a safe URL to redirect after authentication
      -> raise django.core.exceptions.SuspiciousOperation if no state was found

    To remove the state:
    - self.remove_state(state, delay=0)
      -> Will remove the state from Redis; must be called at the end of the request
      -> The delay parameter is the number of second in which the state will be removed

    """

    def __init__(self, *args, **kwargs):
        self.redis = get_redis_connection()
        return super().__init__(*args, **kwargs)

    def _get_key_redis(self, state: str) -> str:
        return f"oauth-state-{state}"

    def _is_matching_cors_domains(self, url_domain) -> bool:
        # make sure the domain is part of the CORS so that's a safe domain to
        # redirect to.
        if url_domain in settings.CORS_ALLOWED_ORIGINS:
            return True
        for domain_pattern in settings.CORS_ALLOWED_ORIGIN_REGEXES:
            if re.match(domain_pattern, url_domain):
                return True
        return False

    def _is_valid_redirection(self, to) -> bool:
        # make sure the redirect url is from a domain we own
        try:
            url = urlparse(to)
        except ValueError:
            return False
        # the url is only a path without domain, it's valid
        only_path = not url.scheme and not url.netloc and url.path
        if only_path:
            return True
        url_domain = f"{url.scheme}://{url.netloc}"
        return self._is_matching_cors_domains(url_domain)

    def _generate_redirection_url(self) -> str:
        redirection_url = self.request.GET.get("to")
        if redirection_url and self._is_valid_redirection(redirection_url):
            return redirection_url
        return (
            f"{settings.CODECOV_DASHBOARD_URL}/{get_short_service_name(self.service)}"
        )

    def generate_state(self) -> str:
        state = uuid.uuid4().hex
        redirection_url = self._generate_redirection_url()
        self.redis.setex(self._get_key_redis(state), 500, redirection_url)
        return state

    def get_redirection_url_from_state(self, state) -> str:
        data = self.redis.get(self._get_key_redis(state))
        if not data:
            raise SuspiciousOperation("Error with authentication please try again")
        return data.decode("utf-8")

    def remove_state(self, state, delay=0) -> None:
        redirection_url = self.get_redirection_url_from_state(state)
        if delay == 0:
            self.redis.delete(self._get_key_redis(state))
        else:
            self.redis.setex(self._get_key_redis(state), delay, redirection_url)


class LoginMixin(object):
    segment_service = SegmentService()

    def get_is_enterprise(self):
        # TODO Change when rolling out enterprise
        return False

    def get_or_create_org(self, single_organization):
        owner, was_created = Owner.objects.get_or_create(
            service=self.service, service_id=single_organization["id"]
        )
        return owner

    def login_from_user_dict(self, user_dict, request, response):
        user_orgs = user_dict["orgs"]
        formatted_orgs = [
            dict(username=org["username"], id=str(org["id"])) for org in user_orgs
        ]
        upserted_orgs = []
        for org in formatted_orgs:
            upserted_orgs.append(self.get_or_create_org(org))

        if self.get_is_enterprise() and get_config(self.service, "organizations"):
            # TODO Change when rolling out enterprise
            pass

        self._check_user_count_limitations()
        user, is_new_user = self._get_or_create_user(user_dict, request)
        fields_to_update = []
        if user_dict.get("is_student") != user.student:
            user.student = user_dict.get("is_student")
            if user.student_created_at is None:
                user.student_created_at = timezone.now()
            user.student_updated_at = timezone.now()
            fields_to_update.extend(
                ["student", "student_created_at", "student_updated_at"]
            )

        if user.organizations is None:
            user.organizations = [o.ownerid for o in upserted_orgs]
            fields_to_update.extend(["organizations"])

        if user.bot is not None:
            log.info(
                "Clearing user bot field",
                extra=dict(ownerid=user.ownerid, old_bot=user.bot),
            )
            user.bot = None
            fields_to_update.append("bot")

        if fields_to_update:
            user.save(update_fields=fields_to_update + ["updatestamp"])

        self._set_proper_cookies_and_session(user, request, response)
        RefreshService().trigger_refresh(user.ownerid, user.username)

        # Login the user if staff via Django authentication. Allows staff users to access Django admin.
        if user.is_staff:
            login(request, user)

        log.info("User is logging in", extra=dict(ownerid=user.ownerid))
        return user

    def _set_proper_cookies_and_session(self, user, request, response):
        domain_to_use = settings.COOKIES_DOMAIN
        Session.objects.filter(
            owner_id=user.ownerid, type="login", ip=request.META.get("REMOTE_ADDR")
        ).delete()
        session = Session(
            owner=user,
            useragent=request.META.get("HTTP_USER_AGENT"),
            ip=request.META.get("REMOTE_ADDR"),
            lastseen=timezone.now(),
            type="login",
        )
        session.save()
        token = str(session.token)
        signed_cookie_value = create_signed_value(
            f"{self.service}-token", token, version=None
        )
        response.set_cookie(
            f"{self.service}-token",
            signed_cookie_value,
            domain=domain_to_use,
            httponly=True,
            secure=True,
            samesite=settings.COOKIE_SAME_SITE,
        )
        response.set_cookie(
            f"{self.service}-username",
            user.username,
            domain=domain_to_use,
            httponly=True,
            secure=True,
            samesite=settings.COOKIE_SAME_SITE,
        )

    def _check_user_count_limitations(self):
        # TODO (Thiago): Do when on enterprise
        pass

    def _get_or_create_user(self, user_dict, request):
        fields_to_update = ["oauth_token", "private_access", "updatestamp"]
        login_data = user_dict["user"]
        owner, was_created = Owner.objects.get_or_create(
            service=f"{self.service}",
            service_id=login_data["id"],
            defaults={"createstamp": timezone.now()},
        )
        if login_data["login"] != owner.username:
            fields_to_update.append("username")
            owner.username = login_data["login"]

        owner.oauth_token = encryptor.encode(login_data["access_token"]).decode()
        owner.private_access = user_dict["has_private_access"]
        if user_dict["user"].get("name"):
            owner.name = user_dict["user"]["name"]
            fields_to_update.append("name")

        if user_dict["user"].get("email"):
            owner.email = user_dict["user"].get("email")
            fields_to_update.append("email")

        owner.save(update_fields=fields_to_update)

        ## Segment tracking
        self.segment_service.identify_user(owner)
        self.segment_service.group(owner)
        marketing_tags = self.retrieve_marketing_tags_from_cookie()
        if was_created:
            self.segment_service.user_signed_up(owner, **marketing_tags)
        else:
            self.segment_service.user_signed_in(owner, **marketing_tags)

        return (owner, was_created)

    # below are functions to save marketing UTM params to cookie to retrieve them
    # on the oauth callback for the tracking functions
    def _get_utm_params(self, params: dict) -> dict:
        filtered_params = {
            "utm_department": params.get("utm_department", None),
            "utm_campaign": params.get("utm_campaign", None),
            "utm_medium": params.get("utm_medium", None),
            "utm_source": params.get("utm_source", None),
            "utm_content": params.get("utm_content", None),
            "utm_term": params.get("utm_term", None),
        }
        # remove None values from the dict
        return {k: v for k, v in filtered_params.items() if v is not None}

    def store_to_cookie_utm_tags(self, response) -> None:
        data = urlencode(self._get_utm_params(self.request.GET))
        response.set_cookie(
            "_marketing_tags",
            data,
            max_age=500,  # Same as state validatiy
            httponly=True,
            domain=settings.COOKIES_DOMAIN,
        )

    def retrieve_marketing_tags_from_cookie(self) -> dict:
        cookie_data = self.request.COOKIES.get("_marketing_tags", "")
        params_as_dict = parse_qs(cookie_data)
        filtered_params = self._get_utm_params(params_as_dict)
        return {k: v[0] for k, v in filtered_params.items()}
