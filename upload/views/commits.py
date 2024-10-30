import logging

from rest_framework.exceptions import NotAuthenticated
from rest_framework.generics import ListCreateAPIView
from shared.metrics import inc_counter

from codecov_auth.authentication.repo_auth import (
    GitHubOIDCTokenAuthentication,
    GlobalTokenAuthentication,
    OrgLevelTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
    TokenlessAuthentication,
    UploadTokenRequiredAuthenticationCheck,
    repo_auth_custom_exception_handler,
)
from core.models import Commit
from upload.helpers import generate_upload_prometheus_metrics_labels
from upload.metrics import API_UPLOAD_COUNTER
from upload.serializers import CommitSerializer
from upload.views.base import GetterMixin
from upload.views.uploads import CanDoCoverageUploadsPermission

log = logging.getLogger(__name__)


class CommitViews(ListCreateAPIView, GetterMixin):
    serializer_class = CommitSerializer
    permission_classes = [CanDoCoverageUploadsPermission]
    authentication_classes = [
        UploadTokenRequiredAuthenticationCheck,
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
        inc_counter(
            API_UPLOAD_COUNTER,
            labels=generate_upload_prometheus_metrics_labels(
                action="coverage",
                endpoint="create_commit",
                request=self.request,
                is_shelter_request=self.is_shelter_request(),
                position="start",
            ),
        )
        repository = self.get_repo()

        commit = serializer.save(repository=repository)

        log.info(
            "Request to create new commit",
            extra=dict(repo=repository.name, commit=commit.commitid),
        )

        inc_counter(
            API_UPLOAD_COUNTER,
            labels=generate_upload_prometheus_metrics_labels(
                action="coverage",
                endpoint="create_commit",
                request=self.request,
                repository=repository,
                is_shelter_request=self.is_shelter_request(),
                position="end",
            ),
        )

        return commit
