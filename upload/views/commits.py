import logging

from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListCreateAPIView

from codecov_auth.authentication.repo_auth import (
    GitHubOIDCTokenAuthentication,
    GlobalTokenAuthentication,
    OrgLevelTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
    TokenlessAuth,
    TokenlessAuthentication,
    repo_auth_custom_exception_handler,
)
from core.models import Commit
from services.task import TaskService
from upload.serializers import CommitSerializer
from upload.views.base import GetterMixin
from upload.views.uploads import CanDoCoverageUploadsPermission

log = logging.getLogger(__name__)


class CommitViews(ListCreateAPIView, GetterMixin):
    serializer_class = CommitSerializer
    permission_classes = [CanDoCoverageUploadsPermission]
    authentication_classes = [
        GlobalTokenAuthentication,
        OrgLevelTokenAuthentication,
        GitHubOIDCTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
        TokenlessAuthentication,
    ]

    def get_exception_handler(self):
        return repo_auth_custom_exception_handler

    def get_queryset(self):
        repository = self.get_repo()
        return Commit.objects.filter(repository=repository)

    def _possibly_fix_branch_name(self, request) -> None:
        """Avoids users being able to overwrite coverage info for a branch
        that exists in the upstream repo with coverage for their fork branch.
        By pre-pending the fork name to the branch
        (the CLI might have done this already)
        """
        # This only affects tokenless uploads
        if not isinstance(request.auth, TokenlessAuth):
            return
        # Notice that at this point we already validated that this fork_slug
        # is the correct repo from the head of a PR to the upstream repo
        # with the git provider
        fork_slug = request.headers.get("X-Tokenless", None)
        branch_info = request.data.get("branch")
        if branch_info is None:
            # There should always be a branch in the request
            raise ValidationError("missing branch")
        # The CLI might have pre-prended the branch with something already
        if ":" in branch_info:
            _, branch_info = branch_info.split(":")
        branch_to_set = f"{fork_slug}:{branch_info}"
        if request.data.get("branch") != branch_to_set:
            request.data["branch"] = branch_to_set

    def create(self, request, *args, **kwargs):
        self._possibly_fix_branch_name(request)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        repository = self.get_repo()
        commit = serializer.save(repository=repository)
        log.info(
            "Request to create new commit",
            extra=dict(repo=repository.name, commit=commit.commitid),
        )
        TaskService().update_commit(
            commitid=commit.commitid, repoid=commit.repository.repoid
        )
        return commit
