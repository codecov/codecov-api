import logging
from typing import Any, Callable

from django.http import HttpRequest, HttpResponseNotAllowed
from rest_framework import status
from rest_framework.generics import ListCreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
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
from core.models import Commit, Repository
from reports.models import CommitReport
from services.task import TaskService
from upload.helpers import (
    generate_upload_prometheus_metrics_labels,
    validate_activated_repo,
)
from upload.metrics import API_UPLOAD_COUNTER
from upload.serializers import CommitReportSerializer
from upload.views.base import GetterMixin
from upload.views.uploads import CanDoCoverageUploadsPermission

log = logging.getLogger(__name__)


def create_report(
    serializer: CommitReportSerializer, repository: Repository, commit: Commit
) -> CommitReport:
    code = serializer.validated_data.get("code")
    if code == "default":
        serializer.validated_data["code"] = None
    instance, was_created = serializer.save(
        commit_id=commit.id,
        report_type=CommitReport.ReportType.COVERAGE,
    )
    if was_created:
        TaskService().preprocess_upload(
            repository.repoid, commit.commitid, instance.code
        )
    return instance


class ReportViews(ListCreateAPIView, GetterMixin):
    serializer_class = CommitReportSerializer
    permission_classes = [CanDoCoverageUploadsPermission]
    authentication_classes = [
        UploadTokenRequiredAuthenticationCheck,
        GlobalTokenAuthentication,
        OrgLevelTokenAuthentication,
        GitHubOIDCTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
        TokenlessAuthentication,
    ]

    def get_exception_handler(self) -> Callable[[Exception, dict[str, Any]], Response]:
        return repo_auth_custom_exception_handler

    def perform_create(self, serializer: CommitReportSerializer) -> CommitReport:
        inc_counter(
            API_UPLOAD_COUNTER,
            labels=generate_upload_prometheus_metrics_labels(
                action="coverage",
                endpoint="create_report",
                request=self.request,
                is_shelter_request=self.is_shelter_request(),
                position="start",
            ),
        )
        repository = self.get_repo()
        validate_activated_repo(repository)
        commit = self.get_commit(repository)
        log.info(
            "Request to create new report",
            extra=dict(repo=repository.name, commit=commit.commitid),
        )
        instance = create_report(serializer, repository, commit)

        inc_counter(
            API_UPLOAD_COUNTER,
            labels=generate_upload_prometheus_metrics_labels(
                action="coverage",
                endpoint="create_report",
                request=self.request,
                repository=repository,
                is_shelter_request=self.is_shelter_request(),
                position="end",
            ),
        )
        return instance

    def list(
        self, request: HttpRequest, service: str, repo: str, commit_sha: str
    ) -> HttpResponseNotAllowed:
        return HttpResponseNotAllowed(permitted_methods=["POST"])


EMPTY_RESPONSE = {
    "state": "completed",
    "result": {
        "state": "deprecated",
        "message": 'The "local upload" functionality has been deprecated.',
    },
}


class ReportResultsView(APIView, GetterMixin):
    permission_classes = [CanDoCoverageUploadsPermission]
    authentication_classes = [
        UploadTokenRequiredAuthenticationCheck,
        GlobalTokenAuthentication,
        OrgLevelTokenAuthentication,
        GitHubOIDCTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
        TokenlessAuthentication,
    ]

    def get_exception_handler(self) -> Callable[[Exception, dict[str, Any]], Response]:
        return repo_auth_custom_exception_handler

    def get(self, request, *args, **kwargs):
        return Response(EMPTY_RESPONSE)

    def post(self, request, *args, **kwargs):
        return Response(EMPTY_RESPONSE, status=status.HTTP_201_CREATED)
