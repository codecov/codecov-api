import hashlib
import hmac
import logging
from base64 import b64decode

from django.contrib.auth.backends import BaseBackend
from django.utils import timezone
from rest_framework import authentication, exceptions

from codecov_auth.helpers import decode_token_from_cookie
from codecov_auth.models import Owner, Session
from utils.config import get_config
from utils.services import get_long_service_name

log = logging.getLogger(__name__)


class CodecovAuthMixin:
    def update_session(self, request, session):
        session.lastseen = timezone.now()
        session.useragent = request.META.get("User-Agent")
        http_x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if http_x_forwarded_for:
            session.ip = http_x_forwarded_for.split(",")[0]
        else:
            session.ip = request.META.get("REMOTE_ADDR")
        session.save(update_fields=["lastseen", "useragent", "ip"])

    def get_user_and_session(self, token, request):
        try:
            session = Session.objects.select_related("owner", "owner__profile").get(
                token=token
            )
        except Session.DoesNotExist:
            raise exceptions.AuthenticationFailed("No such user")
        if (
            "staff_user" in request.COOKIES
            and "service" in request.resolver_match.kwargs
        ):
            return self.attempt_impersonation(
                user=session.owner,
                username_to_impersonate=request.COOKIES["staff_user"],
                service=request.resolver_match.kwargs["service"],
            )
        else:
            self.update_session(request, session)
        return (session.owner, session)

    def attempt_impersonation(self, user, username_to_impersonate, service):
        log.info(
            (
                f"Impersonation attempted --"
                f" {user.username} impersonating {username_to_impersonate}"
            )
        )
        service = get_long_service_name(service)
        if not user.staff:
            log.info(f"Impersonation attempted by non-staff user: {user.username}")
            raise exceptions.PermissionDenied()

        try:
            impersonated_user = Owner.objects.get(
                service=service, username=username_to_impersonate
            )
        except Owner.DoesNotExist:
            log.warning(
                (
                    f"Unsuccessful impersonation of {username_to_impersonate}"
                    f" on service {service}, user doesn't exist"
                )
            )
            raise exceptions.AuthenticationFailed(
                f"No such user to impersonate: {username_to_impersonate}"
            )
        log.info(
            (
                f"Request impersonated -- successful "
                f"impersonation of {username_to_impersonate}, by {user.username}"
            )
        )
        return (impersonated_user, None)

    def decode_token_from_cookie(self, encoded_cookie):
        secret = get_config("setup", "http", "cookie_secret")
        return decode_token_from_cookie(secret, encoded_cookie)

    def get_encoded_token_from_request(self, request):
        # try with a token type header
        token_type = request.META.get("HTTP_TOKEN_TYPE")
        encoded_cookie = request.COOKIES.get(token_type)
        if encoded_cookie:
            return encoded_cookie
        # try with the "service" arg from the route to get the cookie
        service = request.resolver_match.kwargs.get("service")
        return request.COOKIES.get(f"{get_long_service_name(service)}-token")


class CodecovTokenAuthenticationBase(CodecovAuthMixin):
    def authenticate(self, request):
        encoded_cookie = self.get_encoded_token_from_request(request)

        if not encoded_cookie:
            return None

        token = self.decode_token_from_cookie(encoded_cookie)

        return self.get_user_and_session(token, request)


class CodecovTokenAuthenticationBackend(CodecovTokenAuthenticationBase, BaseBackend):
    def get_user(self, ownerid):
        return Owner.objects.filter(ownerid=ownerid).first()


class CodecovTokenAuthentication(
    CodecovTokenAuthenticationBase, authentication.BaseAuthentication
):
    def authenticate_header(self, request):
        return 'Bearer realm="api"'


class CodecovSessionAuthentication(
    authentication.SessionAuthentication, CodecovAuthMixin
):
    """Authenticates based on the user cookie from the old codecov.io tornado system

    This Authenticator works based on the existing authentication method from the current/old
        codecov.io codebase. On tornado, the `set_secure_cookie` writes a base64 encoded
        value for the cookie, along with some metadata and a signature in the end.

    In this context we are not interested in the signature, since it will require a lot of
        code porting from tornado and it is not that beneficial for our code.

    Steps:

        The cookie comes in the format:

            2|1:0|10:1546487835|12:github-token|48:MDZlZDQwNmQtM2ZlNS00ZmY0LWJhYmEtMzQ5NzM5NzMyYjZh|f520039bc6cfb111e4cfc5c3e44fc4fa5921402918547b54383939da803948f4

        We first validate the string, to make sure the last field is the proper signature to the rest

        We then parse it and take the 5th pipe-delimited value

            48:MDZlZDQwNmQtM2ZlNS00ZmY0LWJhYmEtMzQ5NzM5NzMyYjZh

        This is the length + the field itself

            MDZlZDQwNmQtM2ZlNS00ZmY0LWJhYmEtMzQ5NzM5NzMyYjZh

        We base64 decode it and obtain

            06ed406d-3fe5-4ff4-baba-349739732b6a

        Which is the final token

    """

    # TODO: When this handles the /profile route, we will have to
    # add a 'service' url-param there
    def authenticate(self, request):
        encoded_cookie = self.get_encoded_token_from_request(request)

        if not encoded_cookie:
            return None

        self.enforce_csrf(request)

        token = self.decode_token_from_cookie(encoded_cookie)
        return self.get_user_and_session(token, request)
