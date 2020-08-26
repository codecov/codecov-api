from django.utils import timezone
from django.conf import settings

from codecov_auth.helpers import create_signed_value
from codecov_auth.models import Session, Owner
from utils.encryption import encryptor


class LoginMixin(object):
    def login_from_user_dict(self, user_dict, request, response):
        self._check_user_count_limitations()
        user = self._get_or_create_user(user_dict)
        self._track_user_events()
        self._set_proper_cookies_and_session(user, request, response)
        self._schedule_proper_tasks()
        return user

    def _set_proper_cookies_and_session(self, user, request, response):
        # TODO (Thiago): On future backfill task
        domain_to_use = settings.COOKIES_DOMAIN
        session = Session(
            owner=user,
            useragent=request.META.get("HTTP_USER_AGENT"),
            ip=request.META.get("REMOTE_ADDR"),
            lastseen=timezone.now(),
            type="login",
        )
        session.save()
        token = str(session.token)
        signed_cookie_value = create_signed_value("github-token", token, version=None)
        response.set_cookie(
            "github-token", signed_cookie_value, domain=domain_to_use, httponly=True
        )
        response.set_cookie(
            "github-username", user.username, domain=domain_to_use, httponly=True
        )

    def _check_user_count_limitations(self):
        # TODO (Thiago): On future backfill task
        pass

    def _get_or_create_user(self, user_dict):
        owner, was_created = Owner.objects.get_or_create(
            service="github", service_id=user_dict["service_id"]
        )
        owner.oauth_token = encryptor.encode(user_dict["access_token"])
        owner.username = user_dict["username"]
        owner.save()
        return owner

    def _track_user_events(self):
        # TODO (Thiago): On future backfill task
        pass

    def _schedule_proper_tasks(self):
        # TODO (Thiago): On future backfill task
        pass
