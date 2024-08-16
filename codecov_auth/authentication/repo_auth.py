import json
import logging
import re
from datetime import datetime
from typing import Any, List, Tuple
from uuid import UUID

from asgiref.sync import async_to_sync
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import QuerySet
from django.http.request import HttpRequest
from django.utils import timezone
from jwt import PyJWTError
from rest_framework import authentication, exceptions
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated
from rest_framework.response import Response
from rest_framework.views import exception_handler
from sentry_sdk import metrics as sentry_metrics
from shared.metrics import metrics
from shared.torngit.exceptions import TorngitObjectNotFoundError, TorngitRateLimitError

from codecov_auth.authentication.helpers import get_upload_info_from_request_path
from codecov_auth.authentication.types import RepositoryAsUser, RepositoryAuthInterface
from codecov_auth.models import (
    OrganizationLevelToken,
    RepositoryToken,
    Service,
    TokenTypeChoices,
)
from core.models import Commit, Repository
from services.repo_providers import RepoProviderService
from upload.helpers import get_global_tokens, get_repo_with_github_actions_oidc_token
from upload.views.helpers import get_repository_from_string
from utils import is_uuid

log = logging.getLogger(__name__)


def repo_auth_custom_exception_handler(exc, context):
    """
    User arrives here if they have correctly supplied a Token or the Tokenless Headers,
    but their Token has not matched with any of our Authentication methods. The goal is to
    give the user something better than "Invalid Token" or "Authentication credentials were not provided."
    """
    response = exception_handler(exc, context)
    # we were having issues with this block, I made it super cautions.
    # Re-evaluate later whether this is overly cautious.
    if (
        response is not None
        and hasattr(response, "status_code")
        and response.status_code == 401
        and hasattr(response, "data")
    ):
        try:
            exc_code = response.data.get("detail").code
        except (TypeError, AttributeError):
            return response
        if exc_code == NotAuthenticated.default_code:
            response.data["detail"] = (
                "Failed token authentication, please double-check that your repository token matches in the Codecov UI, "
                "or review the docs https://docs.codecov.com/docs/adding-the-codecov-token"
            )
    return response


class LegacyTokenRepositoryAuth(RepositoryAuthInterface):
    def __init__(self, repository, auth_data):
        self._auth_data = auth_data
        self._repository = repository

    def get_scopes(self):
        return [TokenTypeChoices.UPLOAD]

    def get_repositories(self):
        return [self._repository]

    def allows_repo(self, repository):
        return repository in self.get_repositories()


class OIDCTokenRepositoryAuth(LegacyTokenRepositoryAuth):
    pass


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
    def __init__(self, repository: Repository) -> None:
        self._repository = repository

    def get_scopes(self):
        return [TokenTypeChoices.UPLOAD]

    def allows_repo(self, repository):
        return repository in self.get_repositories()

    def get_repositories(self) -> List[Repository]:
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
            repository = Repository.objects.get(upload_token=token)
        except (ValueError, TypeError, Repository.DoesNotExist):
            return None  # continue to next auth class
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
        using_global_token = token in global_tokens
        if not using_global_token:
            return None  # continue to next auth class

        service = global_tokens[token]
        upload_info = get_upload_info_from_request_path(request)
        if upload_info is None:
            return None  # continue to next auth class
        # It's important NOT to use the service returned in upload_info
        # To avoid someone uploading with GlobalUploadToken to a different service
        # Than what it configured
        repository = get_repository_from_string(
            Service(service), upload_info.encoded_slug
        )
        if repository is None:
            raise exceptions.AuthenticationFailed(
                "Could not find a repository, try using repo upload token"
            )
        return (
            RepositoryAsUser(repository),
            LegacyTokenRepositoryAuth(repository, {"token": token}),
        )

    def get_token(self, request: HttpRequest) -> str | None:
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None
        if " " in auth_header:
            _, token = auth_header.split(" ", 1)
            return token
        return auth_header


class OrgLevelTokenAuthentication(authentication.TokenAuthentication):
    def authenticate_credentials(self, key):
        if is_uuid(key):  # else, continue to next auth class
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


class GitHubOIDCTokenAuthentication(authentication.TokenAuthentication):
    def authenticate_credentials(self, token):
        if not token or is_uuid(token):
            return None  # continue to next auth class

        try:
            repository = get_repo_with_github_actions_oidc_token(token)
        except (ObjectDoesNotExist, PyJWTError):
            return None  # continue to next auth class

        log.info(
            "GitHubOIDCTokenAuthentication Success",
            extra=dict(repository=str(repository)),  # Repo<author/name>
        )

        return (
            RepositoryAsUser(repository),
            OIDCTokenRepositoryAuth(repository, {"token": token}),
        )


class TokenlessAuthentication(authentication.TokenAuthentication):
    # TODO: replace this with the message from repo_auth_custom_exception_handler
    auth_failed_message = "Not valid tokenless upload"

    def _get_info_from_request_path(
        self, request: HttpRequest
    ) -> tuple[Repository, str | None]:
        upload_info = get_upload_info_from_request_path(request)

        if upload_info is None:
            raise exceptions.AuthenticationFailed(self.auth_failed_message)
        service, encoded_slug, commitid = upload_info
        # Validate provider
        try:
            service_enum = Service(service)
        except ValueError:
            raise exceptions.AuthenticationFailed(self.auth_failed_message)

        # Validate that next group exists and decode slug
        repo = get_repository_from_string(service_enum, encoded_slug)
        if repo is None:
            # Purposefully using the generic message so that we don't tell that
            # we don't have a certain repo
            raise exceptions.AuthenticationFailed(self.auth_failed_message)

        return repo, commitid

    def get_branch(self, request, repoid=None, commitid=None):
        if repoid and commitid:
            commit = Commit.objects.filter(
                repository_id=repoid, commitid=commitid
            ).first()
            if not commit:
                raise exceptions.AuthenticationFailed(self.auth_failed_message)
            return commit.branch
        else:
            try:
                body = json.loads(str(request.body, "utf8"))
            except json.JSONDecodeError:
                return None
            else:
                return body.get("branch")

    def authenticate(self, request):
        repository, commitid = self._get_info_from_request_path(request)

        if repository is None or repository.private:
            raise exceptions.AuthenticationFailed(self.auth_failed_message)

        branch = self.get_branch(request, repository.repoid, commitid)

        if (branch and ":" in branch) or request.method == "GET":
            return (
                RepositoryAsUser(repository),
                TokenlessAuth(repository),
            )
        else:
            raise exceptions.AuthenticationFailed(self.auth_failed_message)


class BundleAnalysisTokenlessAuthentication(TokenlessAuthentication):
    def _get_info_from_request_path(
        self, request: HttpRequest
    ) -> tuple[Repository, str | None]:
        try:
            body = json.loads(str(request.body, "utf8"))

            # Validate provider
            service_enum = Service(body.get("git_service"))

            # Validate that next group exists and decode slug
            repo = get_repository_from_string(service_enum, body.get("slug"))
            if repo is None:
                # Purposefully using the generic message so that we don't tell that
                # we don't have a certain repo
                raise exceptions.AuthenticationFailed(self.auth_failed_message)

            return repo, body.get("commit")
        except json.JSONDecodeError:
            # Validate request body format
            raise exceptions.AuthenticationFailed(self.auth_failed_message)
        except ValueError:
            # Validate provider
            raise exceptions.AuthenticationFailed(self.auth_failed_message)

    def get_branch(self, request, repoid=None, commitid=None):
        body = json.loads(str(request.body, "utf8"))

        # If commit is not created yet (ie first upload for this commit), we just validate branch format.
        # However if a commit exists already (ie not the first upload for this commit), we must additionally
        # validate the saved commit branch matches what is requested in this upload call.
        commit = Commit.objects.filter(repository_id=repoid, commitid=commitid).first()
        if commit and commit.branch != body.get("branch"):
            raise exceptions.AuthenticationFailed(self.auth_failed_message)

        return body.get("branch")
