import logging

from django.http import HttpRequest, HttpResponseNotAllowed
from rest_framework.generics import CreateAPIView, ListCreateAPIView

from codecov_auth.authentication.repo_auth import (
    GlobalTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
)
from upload.serializers import CommitReportSerializer, ReportResultsSerializer
from upload.views.base import GetterMixin
from upload.views.uploads import CanDoCoverageUploadsPermission

log = logging.getLogger(__name__)


class ReportViews(ListCreateAPIView, GetterMixin):
    serializer_class = CommitReportSerializer
    permission_classes = [CanDoCoverageUploadsPermission]
    authentication_classes = [
        GlobalTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
    ]

    def perform_create(self, serializer):
        repository = self.get_repo()
        commit = self.get_commit(repository)
        log.info(
            "Request to create new report",
            extra=dict(repo=repository.name, commit_id=commit.commitid),
        )
        instance = serializer.save(
            commit_id=commit.id,
        )
        return instance

    def list(self, request: HttpRequest, service: str, repo: str, commit_sha: str):
        return HttpResponseNotAllowed(permitted_methods=["POST"])


class ReportResultsView(CreateAPIView, GetterMixin):
    serializer_class = ReportResultsSerializer
    permission_classes = [CanDoCoverageUploadsPermission]
    authentication_classes = [
        GlobalTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
    ]

    def perform_create(self, serializer):
        repository = self.get_repo()
        commit = self.get_commit(repository)
        report = self.get_report(commit)
        instance = serializer.save(
            report=report,
        )
        return instance
