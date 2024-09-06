import logging

from rest_framework.exceptions import NotAuthenticated
from rest_framework.generics import ListCreateAPIView
from sentry_sdk import metrics as sentry_metrics

from codecov_auth.authentication.repo_auth import (
    GitHubOIDCTokenAuthentication,
    GlobalTokenAuthentication,
    OrgLevelTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
    TokenlessAuthentication,
    repo_auth_custom_exception_handler,
)
from core.models import Commit
from services.task import TaskService
from upload.helpers import generate_upload_sentry_metrics_tags
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

    def list(self, request, *args, **kwargs):
        repository = self.get_repo()
        if repository.private and isinstance(
            self.request.auth, TokenlessAuthentication
        ):
            raise NotAuthenticated()
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        sentry_metrics.incr(
            "upload",
            tags=generate_upload_sentry_metrics_tags(
                action="coverage",
                endpoint="create_commit",
                request=self.request,
                is_shelter_request=self.is_shelter_request(),
                position="start",
            ),
        )
        repository = self.get_repo()

        validated_data = serializer.validated_data
        data_for_create = {**validated_data}
        repo = data_for_create.pop("repository", repository)
        commitid = data_for_create.pop("commitid", None)

        commit, created = Commit.objects.get_or_create(
            repository=repo, commitid=commitid, defaults=data_for_create
        )

        log.info(
            "Request to create new commit",
            extra=dict(repo=repository.name, commit=commit.commitid),
        )
        if created:
            TaskService().update_commit(
                commitid=commit.commitid, repoid=commit.repository.repoid
            )

        sentry_metrics.incr(
            "upload",
            tags=generate_upload_sentry_metrics_tags(
                action="coverage",
                endpoint="create_commit",
                request=self.request,
                repository=repository,
                is_shelter_request=self.is_shelter_request(),
                position="end",
            ),
        )

        serializer.instance = commit
        return serializer.data
