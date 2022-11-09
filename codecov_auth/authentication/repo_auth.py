from typing import List
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import QuerySet
from django.utils import timezone
from rest_framework import authentication, exceptions

from codecov_auth.authentication.types import RepositoryAsUser, RepositoryAuthInterface
from codecov_auth.models import OrganizationLevelToken, Owner, RepositoryToken
from core.models import Repository
from upload.helpers import get_global_tokens


class LegacyTokenRepositoryAuth(RepositoryAuthInterface):
    def __init__(self, repository, auth_data):
        self._auth_data = auth_data
        self._repository = repository

    def get_scopes(self):
        return ["upload"]

    def get_repositories(self):
        return [self._repository]

    def allows_repo(self, repository):
        return repository in self.get_repositories()


class TableTokenRepositoryAuth(RepositoryAuthInterface):
    def __init__(self, repository, token):
        self._token = token
        self._repository = repository

    def get_scopes(self):
        return [self._token.token_type]

    def get_repositories(self):
        return [self._repository]

    def allows_repo(self, repository):
        return repository in self.get_repositories()


class OrgLevelTokenRepositoryAuth(RepositoryAuthInterface):
    def __init__(self, token: OrganizationLevelToken) -> None:
        self._token = token
        self._org = token.owner

    def get_scopes(self):
        return [self._token.token_type]

    def allows_repo(self, repository):
        return repository.author.ownerid == self._org.ownerid

    def get_repositories_queryset(self) -> QuerySet:
        """Returns the QuerySet that generates get_repositories list.
        Because QuerySets are lazy you can add further filters on top of it improving performance.
        """
        return Repository.objects.filter(author=self._org)

    def get_repositories(self) -> List[Repository]:
        # This might be an expensive function depending on the owner in question (thousands of repos)
        # Consider using get_repositories_queryset if possible and adding more filters to it
        return list(Repository.objects.filter(author=self._org).all())


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


class GlobalTokenAuthentication(authentication.TokenAuthentication):
    def authenticate(self, request):
        global_tokens = get_global_tokens()
        token = self.get_token(request)
        repoid = self.get_repoid(request)
        owner = self.get_owner(request)
        using_global_token = True if token in global_tokens else False
        service = global_tokens[token] if using_global_token else None

        if using_global_token:
            try:
                repository = Repository.objects.get(
                    author__service=service,
                    repoid=repoid,
                    author__username=owner.username,
                )
            except ObjectDoesNotExist:
                raise exceptions.AuthenticationFailed(
                    "Could not find a repository, try using repo upload token"
                )
        else:
            return None
        return (
            RepositoryAsUser(repository),
            LegacyTokenRepositoryAuth(repository, {"token": token}),
        )

    def get_token(self, request):
        # TODO
        pass

    def get_repoid(self, request):
        # TODO
        pass

    def get_owner(self, request):
        # TODO
        pass


class OrgLevelTokenAuthentication(authentication.TokenAuthentication):
    def authenticate_credentials(self, key):
        if settings.IS_ENTERPRISE:
            return None
        # Actual verification for org level tokens
        token = OrganizationLevelToken.objects.filter(token=key).first()

        if token is None:
            return None
        if token.valid_until and token.valid_until <= timezone.now():
            raise exceptions.AuthenticationFailed("Token is expired.")

        return (
            token.owner,
            OrgLevelTokenRepositoryAuth(token),
        )
