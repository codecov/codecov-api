import re
from typing import List, Optional, Tuple
from uuid import UUID

from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import QuerySet
from django.utils import timezone
from rest_framework import authentication, exceptions
from shared.torngit.exceptions import TorngitObjectNotFoundError

from codecov_auth.authentication.types import RepositoryAsUser, RepositoryAuthInterface
from codecov_auth.models import OrganizationLevelToken, Owner, RepositoryToken, Service
from core.models import Repository
from rollouts import TOKENLESS_AUTH_BY_OWNER_SLUG, owner_slug
from services.repo_providers import RepoProviderService
from upload.helpers import get_global_tokens
from upload.views.helpers import get_repository_from_string


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


class TokenlessAuth(RepositoryAuthInterface):
    def __init__(self) -> None:
        pass

    def get_scopes(self):
        raise NotImplementedError()

    def allows_repo(self, repository):
        raise NotImplementedError()

    def get_repositories_queryset(self) -> QuerySet:
        """Returns the QuerySet that generates get_repositories list.
        Because QuerySets are lazy you can add further filters on top of it improving performance.
        """
        raise NotImplementedError()

    def get_repositories(self) -> List[Repository]:
        # This might be an expensive function depending on the owner in question (thousands of repos)
        # Consider using get_repositories_queryset if possible and adding more filters to it
        raise NotImplementedError()


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


class TokenlessAuthentication(authentication.TokenAuthentication):
    """This is named ironically, but provides authentication for tokenless uploads.
    Tokenless only works in FORKs of PUBLIC repos.
    It allows PRs from external contributors (forks) to upload coverage
    for the upstream repo when running in a PR.

    While it uses the same "shell" (authentication.TOkenAuthentication)
    it doesn't really rely on tokens to authenticate.
    """

    auth_failed_message = "Not valid tokenless upload"

    def _get_repo_info_from_request_path(self, request) -> Repository:
        path_info = request.get_full_path_info()
        # The repo part comes from https://stackoverflow.com/a/22312124
        upload_views_prefix_regex = r"\/upload\/(\w+)\/([\w\.@:_/-~]+)\/commits"
        match = re.search(upload_views_prefix_regex, path_info)

        if match is None:
            raise exceptions.AuthenticationFailed(self.auth_failed_message)
        # Validate provider
        service = match.group(1)
        try:
            service_enum = Service(service)
            # Currently only Github is supported
            # TODO [codecov/engineering-team#914]: Extend tokenless support to other providers
            if service_enum != Service.GITHUB:
                raise exceptions.AuthenticationFailed(self.auth_failed_message)
        except ValueError:
            raise exceptions.AuthenticationFailed(self.auth_failed_message)
        # Validate that next group exists and decode slug
        encoded_slug = match.group(2)
        repo = get_repository_from_string(service_enum, encoded_slug)
        if repo is None:
            # Purposefully using the generic message so that we don't tell that
            # we don't have a certain repo
            raise exceptions.AuthenticationFailed(self.auth_failed_message)
        return repo

    @async_to_sync
    async def get_pull_request_info(self, repository_service, fork_pr: str):
        try:
            return await repository_service.get_pull_request(fork_pr)
        except TorngitObjectNotFoundError:
            raise exceptions.AuthenticationFailed(self.auth_failed_message)

    def authenticate(self, request):
        fork_slug = request.headers.get("X-Tokenless", None)
        fork_pr = request.headers.get("X-Tokenless-PR", None)
        if fork_slug is None or fork_pr is None:
            raise exceptions.AuthenticationFailed(self.auth_failed_message)
        # Get the repo
        repository = self._get_repo_info_from_request_path(request)
        # Tokneless is only for public repos
        if repository.private:
            raise exceptions.AuthenticationFailed(self.auth_failed_message)
        # Adding a Feature to this for internal testing
        # before wide release
        # TODO: remove Feature after tokenless goes to general access
        if not TOKENLESS_AUTH_BY_OWNER_SLUG.check_value(
            owner_slug(repository.author), default=False
        ):
            raise exceptions.AuthenticationFailed(self.auth_failed_message)
        # Get the provider service to check the tokenless claim
        repository_service = RepoProviderService().get_adapter(
            repository.author, repository
        )
        pull_request = self.get_pull_request_info(repository_service, fork_pr)
        if (
            pull_request["base"]["slug"]
            != f"{repository.author.username}/{repository.name}"
            or pull_request["head"]["slug"] != fork_slug
        ):
            raise exceptions.AuthenticationFailed(self.auth_failed_message)

        return (
            RepositoryAsUser(repository),
            TokenlessAuth(),
        )
