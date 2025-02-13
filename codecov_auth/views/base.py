import logging
import re
import uuid
from functools import reduce
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.sessions.models import Session as DjangoSession
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http.request import HttpRequest
from django.http.response import HttpResponse
from django.utils import timezone
from django.utils.timezone import now
from shared.encryption.token import encode_token
from shared.events.amplitude import AmplitudeEventPublisher
from shared.license import LICENSE_ERRORS_MESSAGES, get_current_license

from codecov_auth.models import Owner, OwnerProfile, Session, User
from services.analytics import AnalyticsService
from services.redis_configuration import get_redis_connection
from services.refresh import RefreshService
from utils.config import get_config
from utils.encryption import encryptor
from utils.services import get_long_service_name, get_short_service_name

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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.redis = get_redis_connection()
        super().__init__(*args, **kwargs)

    def _session_key(self) -> str:
        return f"{self.service}_oauth_state"

    def _get_key_redis(self, state: str) -> str:
        return f"oauth-state-{state}"

    def _is_matching_cors_domains(self, url_domain: str) -> bool:
        # make sure the domain is part of the CORS so that's a safe domain to
        # redirect to.
        if url_domain in settings.CORS_ALLOWED_ORIGINS:
            return True
        for domain_pattern in settings.CORS_ALLOWED_ORIGIN_REGEXES:
            if re.match(domain_pattern, url_domain):
                return True
        return False

    def _is_valid_redirection(self, to: str) -> bool:
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

        # By saving the state in a session cookie, we can ensure that the user
        # following the redirection URL after OAuth authorization is the same
        # as the user who initiated it. Otherwise, a trickster could generate
        # a final redirect URL to log into their account, send it to some
        # victim, and trick the victim into linking their account with the
        # trickster's.
        self.request.session[self._session_key()] = state

        return state

    def verify_state(self, state: str) -> bool:
        state_from_session = self.request.session.get(self._session_key(), None)
        return state_from_session and state == state_from_session

    def get_redirection_url_from_state(self, state: str) -> tuple[str, bool]:
        cached_url = self.redis.get(self._get_key_redis(state))

        if not cached_url:
            # we come here after an installation event if the setup url is not set correctly, in that case we usually don't
            # have the state set, because that only happens when users try to login, therefore we should just ignore
            # this case and redirect them to what the setup url should be
            return (
                f"{settings.CODECOV_DASHBOARD_URL}/{get_short_service_name(self.service)}",
                False,
            )

        # At this point the git provider has redirected the user back to our
        # site. If the state that the git provider relayed in that redirect
        # matches the state that we have saved in our session cookie, everything
        # is fine and we should return the final redirect URL to complete the
        # login. If we're missing that cookie, or if its state doesn't match up,
        # we want don't to allow the login.
        if not self.verify_state(state):
            log.warning(
                "Warning: login request is missing state or has disagreeing state"
            )
            return (
                f"{settings.CODECOV_DASHBOARD_URL}",
                False,
            )

        # Return the final redirect URL to complete the login.
        return (cached_url.decode("utf-8"), True)

    def remove_state(self, state: str, delay: int = 0) -> None:
        redirection_url, _ = self.get_redirection_url_from_state(state)
        if delay == 0:
            self.redis.delete(self._get_key_redis(state))
        else:
            self.redis.setex(self._get_key_redis(state), delay, redirection_url)

        session_state = self.request.session.get(self._session_key(), None)
        if session_state and session_state == state:
            self.request.session.pop(self._session_key(), None)


class LoginMixin(object):
    analytics_service = AnalyticsService()

    def modify_redirection_url_based_on_default_user_org(
        self, url: str, owner: Owner
    ) -> str:
        if (
            url
            != f"{settings.CODECOV_DASHBOARD_URL}/{get_short_service_name(self.service)}"
            and url
            != f"{settings.CODECOV_DASHBOARD_URL}/{get_long_service_name(self.service)}"
        ):
            return url

        owner_profile = None
        if owner:
            owner_profile = OwnerProfile.objects.filter(owner_id=owner.ownerid).first()
        if owner_profile is not None and owner_profile.default_org is not None:
            url += f"/{owner_profile.default_org.username}"
        return url

    def get_or_create_org(self, single_organization: dict) -> Owner:
        owner, was_created = Owner.objects.get_or_create(
            service=self.service,
            service_id=single_organization["id"],
            defaults={"createstamp": timezone.now()},
        )
        return owner

    def login_owner(
        self, owner: Owner, request: HttpRequest, response: HttpResponse
    ) -> None:
        # if there's a currently authenticated user
        if request.user is not None and not request.user.is_anonymous:
            if owner.user is None:
                # TEMPORARY: We have no mechanism in the UI for supporting multiple
                # owners of the same service linked to the same user.  If the current
                # user is already linked to an owner of the same service as this one then
                # we'll logout the current user, create a new user and link the owner to
                # that new user.  This is not ideal since it creates multiple user records
                # for the same person that will need to be merged later on.
                if request.user.owners.filter(service=owner.service).exists():
                    logout(request)
                    current_user = User.objects.create(
                        email=owner.email,
                        name=owner.name,
                        is_staff=owner.staff,
                    )
                    owner.user = current_user
                    owner.save()
                    login(request, current_user)
                else:
                    # assign the owner to the currently authenticated user
                    owner.user = request.user
                    owner.save()
                    log.info(
                        "User claimed owner",
                        extra=dict(user_id=request.user.pk, ownerid=owner.ownerid),
                    )
            elif request.user != owner.user:
                log.warning(
                    "Owner already linked to another user",
                    extra=dict(user_id=request.user.pk, ownerid=owner.ownerid),
                )
                # TEMPORARY: We may want to handle this better in the future by indicating
                # the issue to the user and letting them decide how to proceeed.  For now
                # we'll just logout the current user and login the user that controls the owner
                # that just OAuth-ed.
                logout(request)
                login(request, owner.user)
                return
        # else we do not have a currently authenticated user
        else:
            current_user = None
            if owner.user is not None:
                current_user = owner.user
            else:
                # no current user and owner has not already been assigned a user
                current_user = User.objects.create(
                    email=owner.email,
                    name=owner.name,
                    is_staff=owner.staff,
                )
                owner.user = current_user
                owner.save()

            login(request, current_user)
            log.info(
                "User logged in",
                extra=dict(user_id=request.user.pk, ownerid=owner.ownerid),
            )

        request.session["current_owner_id"] = owner.pk
        RefreshService().trigger_refresh(owner.ownerid, owner.username)

        self.delete_expired_sessions_and_django_sessions(owner)
        self.store_login_session(owner)

    def get_and_modify_owner(self, user_dict: dict, request: HttpRequest) -> Owner:
        user_orgs = user_dict["orgs"]
        formatted_orgs = [
            dict(username=org["username"], id=str(org["id"])) for org in user_orgs
        ]

        self._check_enterprise_organizations_membership(user_dict, formatted_orgs)
        upserted_orgs = [self.get_or_create_org(org) for org in formatted_orgs]

        self._check_user_count_limitations(user_dict["user"])
        owner, is_new_user = self._get_or_create_owner(user_dict, request)
        fields_to_update = []
        if (
            not get_config(self.service, "student_disabled", default=False)
            and user_dict.get("is_student") != owner.student
        ):
            owner.student = user_dict.get("is_student")
            if owner.student_created_at is None:
                owner.student_created_at = timezone.now()
            owner.student_updated_at = timezone.now()
            fields_to_update.extend(
                ["student", "student_created_at", "student_updated_at"]
            )

        # Updated by the task `SyncTeams` that is called after login.
        # We will only set this for the initial "oranizations is none" login.
        if owner.organizations is None:
            owner.organizations = [o.ownerid for o in upserted_orgs]
            fields_to_update.extend(["organizations"])

        if owner.bot is not None:
            log.info(
                "Clearing user bot field",
                extra=dict(ownerid=owner.ownerid, old_bot=owner.bot),
            )
            owner.bot = None
            fields_to_update.append("bot")

        if fields_to_update:
            owner.save(update_fields=fields_to_update + ["updatestamp"])

        return owner

    def _check_enterprise_organizations_membership(
        self, user_dict: dict, orgs: list[dict]
    ) -> None:
        """Checks if a user belongs to the restricted organizations (or teams if GitHub) allowed in settings."""
        if settings.IS_ENTERPRISE and get_config(self.service, "organizations"):
            orgs_in_settings = set(get_config(self.service, "organizations"))
            orgs_in_user = {org["username"] for org in orgs}
            if not (orgs_in_settings & orgs_in_user):
                raise PermissionDenied(
                    "You must be a member of an organization listed in the Codecov Enterprise setup."
                )
            if get_config(self.service, "teams") and "teams" in user_dict:
                teams_in_settings = set(get_config(self.service, "teams"))
                teams_in_user = {team["name"] for team in user_dict["teams"]}
                if not (teams_in_settings & teams_in_user):
                    raise PermissionDenied(
                        "You must be a member of an allowed team in your organization."
                    )

    def _check_user_count_limitations(self, login_data: dict) -> None:
        if not settings.IS_ENTERPRISE:
            return
        license = get_current_license()
        if not license.is_valid:
            return

        try:
            user_logging_in_if_exists = Owner.objects.get(
                service=f"{self.service}", service_id=login_data["id"]
            )
        except Owner.DoesNotExist:
            user_logging_in_if_exists = None

        if license.number_allowed_users:
            if license.is_pr_billing:
                # User is consuming seat if found in _any_ owner's plan_activated_users
                is_consuming_seat = user_logging_in_if_exists and Owner.objects.filter(
                    plan_activated_users__contains=[user_logging_in_if_exists.ownerid]
                )
                if not is_consuming_seat:
                    owners_with_activated_users = Owner.objects.exclude(
                        plan_activated_users__len=0
                    ).exclude(plan_activated_users__isnull=True)
                    all_distinct_actiaved_users: set[str] = reduce(
                        lambda acc, curr: set(curr.plan_activated_users) | acc,
                        owners_with_activated_users,
                        set(),
                    )
                    if len(all_distinct_actiaved_users) > license.number_allowed_users:
                        raise PermissionDenied(
                            LICENSE_ERRORS_MESSAGES["users-exceeded"]
                        )
            elif not user_logging_in_if_exists or (
                user_logging_in_if_exists and not user_logging_in_if_exists.oauth_token
            ):
                users_on_service_count = Owner.objects.filter(
                    oauth_token__isnull=False, service=f"{self.service}"
                ).count()
                if users_on_service_count > license.number_allowed_users:
                    raise PermissionDenied(LICENSE_ERRORS_MESSAGES["users-exceeded"])

    def _get_or_create_owner(
        self, user_dict: dict, request: HttpRequest
    ) -> tuple[Owner, bool]:
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

        owner.oauth_token = encryptor.encode(encode_token(login_data)).decode()
        owner.private_access = user_dict["has_private_access"]
        if user_dict["user"].get("name"):
            owner.name = user_dict["user"]["name"]
            fields_to_update.append("name")

        if user_dict["user"].get("email"):
            owner.email = user_dict["user"].get("email")
            fields_to_update.append("email")

        owner.save(update_fields=fields_to_update)

        marketing_tags = self.retrieve_marketing_tags_from_cookie()
        amplitude = AmplitudeEventPublisher()
        if was_created:
            self.analytics_service.user_signed_up(owner, **marketing_tags)
            amplitude.publish("User Created", {"user_ownerid": owner.ownerid})
        else:
            self.analytics_service.user_signed_in(owner, **marketing_tags)
            amplitude.publish("User Logged in", {"user_ownerid": owner.ownerid})
        orgs = owner.organizations
        amplitude.publish(
            "set_orgs",
            {
                "user_ownerid": owner.ownerid,
                "org_ids": orgs if orgs is not None else [],
            },
        )

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

    def store_to_cookie_utm_tags(self, response: HttpResponse) -> None:
        if not settings.IS_ENTERPRISE:
            data = urlencode(self._get_utm_params(self.request.GET))
            response.set_cookie(
                "_marketing_tags",
                data,
                max_age=86400,  # Same as state validatiy
                httponly=True,
                domain=settings.COOKIES_DOMAIN,
            )

    def retrieve_marketing_tags_from_cookie(self) -> dict:
        if not settings.IS_ENTERPRISE:
            cookie_data = self.request.COOKIES.get("_marketing_tags", "")
            params_as_dict = parse_qs(cookie_data)
            filtered_params = self._get_utm_params(params_as_dict)
            return {k: v[0] for k, v in filtered_params.items()}
        else:
            return {}

    def store_login_session(self, owner: Owner) -> None:
        # Store user's login session info after logging in
        http_x_forwarded_for = self.request.META.get("HTTP_X_FORWARDED_FOR")
        if http_x_forwarded_for:
            ip = http_x_forwarded_for.split(",")[0]
        else:
            ip = self.request.META.get("REMOTE_ADDR")

        login_session = DjangoSession.objects.filter(
            session_key=self.request.session.session_key
        ).first()

        Session.objects.create(
            lastseen=timezone.now(),
            useragent=self.request.META.get("HTTP_USER_AGENT"),
            ip=ip,
            login_session=login_session,
            type=Session.SessionType.LOGIN,
            owner=owner,
        )

    def delete_expired_sessions_and_django_sessions(self, owner: Owner) -> None:
        """
        This function deletes expired login sessions for a given owner
        """
        with transaction.atomic():
            # Get the primary keys of expired DjangoSessions for the given owner
            expired_sessions = Session.objects.filter(
                owner=owner,
                type="login",
                login_session__isnull=False,
                login_session__expire_date__lt=now(),
            )

            # Delete the rows in the Session table using sessionid
            Session.objects.filter(
                sessionid__in=[es.sessionid for es in expired_sessions]
            ).delete()

            # Delete the rows in the DjangoSession table using the extracted keys
            DjangoSession.objects.filter(
                session_key__in=[es.login_session for es in expired_sessions]
            ).delete()
