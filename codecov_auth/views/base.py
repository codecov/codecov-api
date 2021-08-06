import string
import random
from json import dumps
import logging
from urllib.parse import urlparse
from contextlib import suppress

from django.utils import timezone
from django.conf import settings
from django.contrib.auth import login
from django.core.exceptions import SuspiciousOperation

from codecov_auth.helpers import create_signed_value
from codecov_auth.models import Session, Owner
from utils.encryption import encryptor
from utils.config import get_config
from utils.services import get_short_service_name
from services.refresh import RefreshService
from services.segment import SegmentService
from services.redis_configuration import get_redis_connection


log = logging.getLogger(__name__)


class StateMixin(object):
    def __init__(self, *args, **kwargs):
        self.redis = get_redis_connection()
        return super().__init__(*args, **kwargs)

    def _get_key_redis(self, state: str) -> str:
        return f"oauth-state-{state}"

    def _assert_valid_redirection(self, to):
        # make sure the redirect url is from a domain we own
        with suppress(ValueError):
            url = urlparse(to)
        # the url coudn't be parsed, not valid
        if not url:
            return False
        # the url is only a path without domain, it's valid
        only_path = not url.scheme and not url.netloc and url.path
        if only_path:
            return True
        # make sure the domain is part of the CORS so that's a safe domain to
        # redirect to.
        url_domain = f"{url.scheme}://{url.netloc}"
        if url_domain in settings.CORS_ALLOWED_ORIGINS:
            return True
        for domain_pattern in settings.CORS_ALLOWED_ORIGIN_REGEXES:
            if re.match(domain_pattern, url_domain):
                return True
        return False

    def generate_redirection_url(self) -> str:
        redirection_url = self.request.GET.get("to")
        if self._assert_valid_redirection(redirection_url):
            return redirection_url
        return (
            f"{settings.CODECOV_DASHBOARD_URL}/{get_short_service_name(self.service)}"
        )

    def generate_state(self) -> str:
        possible_keys = string.ascii_uppercase + string.digits
        state = "".join(random.choices(possible_keys, k=16))
        redirection_url = self.generate_redirection_url()
        self.redis.setex(self._get_key_redis(state), 500, redirection_url)
        return state

    def get_redirection_url_from_state(self, state):
        data = self.redis.get(self._get_key_redis(state))
        if not data:
            raise SuspiciousOperation("Error with authentication please try again")
        return data.decode("utf-8")


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
            samesite="Lax",
        )
        response.set_cookie(
            f"{self.service}-username",
            user.username,
            domain=domain_to_use,
            httponly=True,
            secure=True,
            samesite="Lax",
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
        if was_created:
            self.segment_service.user_signed_up(owner, **request.GET.dict())
        else:
            self.segment_service.user_signed_in(owner, **request.GET.dict())

        return (owner, was_created)
