import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework import authentication, exceptions

from codecov_auth.authentication.types import (
    InternalToken,
    InternalUser,
    SuperToken,
    SuperUser,
)
from codecov_auth.models import UserToken

log = logging.getLogger(__name__)


class UserTokenAuthentication(authentication.TokenAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        # we save the request here so that we can set `current_owner` below
        self.request = request
        res = super().authenticate(request)
        self.request = None
        return res

    def authenticate_credentials(self, token):
        try:
            token = UserToken.objects.select_related("owner").get(token=token)
        except (UserToken.DoesNotExist, ValidationError):
            raise exceptions.AuthenticationFailed("Invalid token.")

        if token.valid_until is not None and token.valid_until <= timezone.now():
            raise exceptions.AuthenticationFailed("Invalid token.")

        if self.request:
            # some permissions checking relies on this being available
            self.request.current_owner = token.owner

        # NOTE: this is a bit unconventional in that it will result in
        # `request.user` being an `Owner` instance instead of a `User`.
        # If we returend `token.owner.user` here instead then we'd potentially
        # break existing API clients with tokens being used on behalf of owners
        # that have not logged into Codecov (and created a corresponding user record).
        # i.e. `token.owner.user` could potentially be `None`
        return (token.owner, token)


class SuperTokenAuthentication(authentication.TokenAuthentication):
    keyword = "Bearer"

    def authenticate_credentials(self, key):
        if key == settings.SUPER_API_TOKEN:
            return (SuperUser(), SuperToken(token=key))
        return None


class InternalTokenAuthentication(authentication.TokenAuthentication):
    keyword = "Bearer"

    def authenticate_credentials(self, key):
        if key == settings.CODECOV_INTERNAL_TOKEN:
            return (InternalUser(), InternalToken(token=key))

        raise exceptions.AuthenticationFailed("Invalid token.")


class SessionAuthentication(authentication.SessionAuthentication):
    def enforce_csrf(self, request):
        # disable CSRF for the REST API
        pass
