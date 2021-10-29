from uuid import UUID

from django.utils import timezone
from rest_framework import authentication, exceptions

from codecov_auth.authentication.types import RepositoryAsUser, RepositoryAuthInterface
from codecov_auth.models import RepositoryToken
from core.models import Repository


class LegacyTokenRepositoryAuth(RepositoryAuthInterface):
    def __init__(self, repository, auth_data):
        self._auth_data = auth_data
        self._repository = repository

    def get_scopes(self):
        return ["upload"]

    def get_repositories(self):
        return [self._repository]


class TableTokenRepositoryAuth(RepositoryAuthInterface):
    def __init__(self, repository, token):
        self._token = token
        self._repository = repository

    def get_scopes(self):
        return [self._token.token_type]

    def get_repositories(self):
        return [self._repository]


class RepositoryLegacyQueryTokenAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        token = request.GET.get("token")
        if not token:
            return None
        try:
            token = UUID(token)
        except ValueError:
            return None
        try:
            repository = Repository.objects.get(upload_token=token)
        except Repository.DoesNotExist:
            return None
        return (
            RepositoryAsUser(repository),
            LegacyTokenRepositoryAuth(repository, {"token": token}),
        )


class RepositoryLegacyTokenAuthentication(authentication.TokenAuthentication):
    def authenticate_credentials(self, token):
        try:
            token = UUID(token)
        except (ValueError, TypeError):
            raise exceptions.AuthenticationFailed("Invalid token.")
        try:
            repository = Repository.objects.get(upload_token=token)
        except Repository.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid token.")
        return (
            RepositoryAsUser(repository),
            LegacyTokenRepositoryAuth(repository, {"token": token}),
        )


class RepositoryTokenAuthentication(authentication.TokenAuthentication):
    keyword = "Repotoken"

    def authenticate_credentials(self, key):
        try:
            token = RepositoryToken.objects.select_related("repository").get(key=key)
        except RepositoryToken.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid token.")

        if not token.repository.active:
            raise exceptions.AuthenticationFailed("User inactive or deleted.")
        if token.valid_until is not None and token.valid_until <= timezone.now():
            raise exceptions.AuthenticationFailed("Invalid token.")
        return (
            RepositoryAsUser(token.repository),
            TableTokenRepositoryAuth(token.repository, token),
        )
