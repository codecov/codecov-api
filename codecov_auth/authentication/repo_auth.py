import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils import timezone
from jwt import PyJWTError
from rest_framework import authentication, exceptions, serializers
from rest_framework.exceptions import NotAuthenticated, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler
from shared.django_apps.codecov_auth.models import Owner

from codecov_auth.authentication.helpers import get_upload_info_from_request_path
from codecov_auth.authentication.types import RepositoryAsUser, RepositoryAuthInterface
from codecov_auth.models import (
    OrganizationLevelToken,
    RepositoryToken,
    Service,
    TokenTypeChoices,
)
from core.models import Commit, Repository
from upload.helpers import get_global_tokens, get_repo_with_github_actions_oidc_token
from upload.views.helpers import (
    get_repository_and_owner_from_string,
    get_repository_from_string,
)
from utils import is_uuid

log = logging.getLogger(__name__)


def repo_auth_custom_exception_handler(
    exc: Exception, context: Dict[str, Any]
) -> Response:
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
    def __init__(self, repository: Repository, auth_data: Dict[str, Any]) -> None:
        self._auth_data = auth_data
        self._repository = repository

    def get_scopes(self) -> List[TokenTypeChoices]:
        return [TokenTypeChoices.UPLOAD]

    def get_repositories(self) -> List[Repository]:
        return [self._repository]

    def allows_repo(self, repository: Repository) -> bool:
        return repository in self.get_repositories()


class OIDCTokenRepositoryAuth(LegacyTokenRepositoryAuth):
    pass


class TableTokenRepositoryAuth(RepositoryAuthInterface):
    def __init__(self, repository: Repository, token: RepositoryToken) -> None:
        self._token = token
        self._repository = repository

    def get_scopes(self) -> List[str]:
        return [self._token.token_type]

    def get_repositories(self) -> List[Repository]:
        return [self._repository]

    def allows_repo(self, repository: Repository) -> bool:
        return repository in self.get_repositories()


class OrgLevelTokenRepositoryAuth(RepositoryAuthInterface):
    def __init__(self, token: OrganizationLevelToken) -> None:
        self._token = token
        self._org = token.owner

    def get_scopes(self) -> List[str]:
        return [self._token.token_type]

    def allows_repo(self, repository: Repository) -> bool:
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

    def get_scopes(self) -> List[TokenTypeChoices]:
        return [TokenTypeChoices.UPLOAD]

    def allows_repo(self, repository: Repository) -> bool:
        return repository in self.get_repositories()

    def get_repositories(self) -> List[Repository]:
        return [self._repository]


class RepositoryLegacyQueryTokenAuthentication(authentication.BaseAuthentication):
    def authenticate(
        self, request: HttpRequest
    ) -> Optional[Tuple[RepositoryAsUser, LegacyTokenRepositoryAuth]]:
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
    def authenticate_credentials(
        self, token: str
    ) -> Optional[Tuple[RepositoryAsUser, LegacyTokenRepositoryAuth]]:
        try:
            token_uuid = UUID(token)
            repository = Repository.objects.get(upload_token=token_uuid)
        except (ValueError, TypeError, Repository.DoesNotExist):
            return None  # continue to next auth class
        return (
            RepositoryAsUser(repository),
            LegacyTokenRepositoryAuth(repository, {"token": token_uuid}),
        )


class RepositoryTokenAuthentication(authentication.TokenAuthentication):
    keyword = "Repotoken"

    def authenticate_credentials(
        self, key: str
    ) -> Optional[Tuple[RepositoryAsUser, TableTokenRepositoryAuth]]:
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
    def authenticate(
        self, request: HttpRequest
    ) -> Optional[Tuple[RepositoryAsUser, LegacyTokenRepositoryAuth]]:
        global_tokens = get_global_tokens()
        token = self.get_token(request)
        using_global_token = token in global_tokens
        if not using_global_token:
            return None  # continue to next auth class

        service = global_tokens.get(token, "")
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
    def authenticate_credentials(
        self, key: str
    ) -> Optional[Tuple[Owner, OrgLevelTokenRepositoryAuth]]:
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
    def authenticate_credentials(
        self, token: str
    ) -> Optional[Tuple[RepositoryAsUser, OIDCTokenRepositoryAuth]]:
        if not token or is_uuid(token):
            return None  # continue to next auth class

        try:
            repository = get_repo_with_github_actions_oidc_token(token)
        except (ObjectDoesNotExist, PyJWTError, ValidationError):
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

    def get_branch(
        self,
        request: HttpRequest,
        repoid: Optional[int] = None,
        commitid: Optional[str] = None,
    ) -> Optional[str]:
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

    def authenticate(
        self, request: HttpRequest
    ) -> Tuple[RepositoryAsUser, TokenlessAuth]:
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

    def get_branch(
        self,
        request: HttpRequest,
        repoid: Optional[int] = None,
        commitid: Optional[str] = None,
    ) -> str:
        body = json.loads(str(request.body, "utf8"))

        # If commit is not created yet (ie first upload for this commit), we just validate branch format.
        # However, if a commit exists already (ie not the first upload for this commit), we must additionally
        # validate the saved commit branch matches what is requested in this upload call.
        commit = Commit.objects.filter(repository_id=repoid, commitid=commitid).first()
        if commit and commit.branch != body.get("branch"):
            raise exceptions.AuthenticationFailed(self.auth_failed_message)

        return body.get("branch")


class UploadTokenRequiredAuthenticationCheck(authentication.TokenAuthentication):
    """
    If repo is public, OwnerOrg can set upload_token_required_for_public_repos=False
    to allow uploads with no token. If this is the case, catch it first and exclude from
    other Auth checks.
    """

    def _get_info_from_request_path(
        self, request: HttpRequest
    ) -> tuple[Repository | None, Owner | None]:
        upload_info = get_upload_info_from_request_path(request)

        if upload_info is None:
            return None, None  # continue to next auth class
        service, encoded_slug, _ = upload_info
        # Validate provider
        try:
            service_enum = Service(service)
        except ValueError:
            return None, None  # continue to next auth class

        repository, owner = get_repository_and_owner_from_string(
            service_enum, encoded_slug
        )

        return repository, owner

    def get_repository_and_owner(
        self, request: HttpRequest
    ) -> tuple[Repository | None, Owner | None]:
        return self._get_info_from_request_path(request)

    def authenticate(
        self, request: HttpRequest
    ) -> tuple[RepositoryAsUser, TokenlessAuth] | None:
        repository, owner = self.get_repository_and_owner(request)

        if (
            repository is None
            or repository.private
            or owner is None
            or owner.upload_token_required_for_public_repos
        ):
            return None  # continue to next auth class

        return (
            RepositoryAsUser(repository),
            TokenlessAuth(repository),
        )


class UploadTokenRequiredGetFromBodySerializer(serializers.Serializer):
    slug = serializers.CharField(required=True)
    service = serializers.CharField(required=False)  # git_service from TA
    git_service = serializers.CharField(required=False)  # git_service from BA


class UploadTokenRequiredGetFromBodyAuthenticationCheck(
    UploadTokenRequiredAuthenticationCheck
):
    """
    Get Repository and Owner from request body instead of path,
    then use the same authenticate() as parent class.
    """

    def _get_git(self, validated_data: Dict[str, str]) -> Optional[str]:
        """
        BA sends this in as git_service, TA sends this in as service.
        Use this function so this Check class can be used by both views.
        """
        git_service = validated_data.get("git_service") or validated_data.get("service")
        return git_service

    def _get_info_from_request_body(
        self, request: HttpRequest
    ) -> tuple[Repository | None, Owner | None]:
        try:
            body = json.loads(str(request.body, "utf8"))

            serializer = UploadTokenRequiredGetFromBodySerializer(data=body)

            if serializer.is_valid():
                git_service = self._get_git(validated_data=serializer.validated_data)
                service_enum = Service(git_service)
                return get_repository_and_owner_from_string(
                    service=service_enum,
                    repo_identifier=serializer.validated_data["slug"],
                )

        except (json.JSONDecodeError, ValueError):
            # exceptions raised by json.loads() and Service()
            # catch rather than raise to continue to next auth class
            pass

        return None, None  # continue to next auth class

    def get_repository_and_owner(
        self, request: HttpRequest
    ) -> tuple[Repository | None, Owner | None]:
        return self._get_info_from_request_body(request)
