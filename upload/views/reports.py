import logging

from django.http import HttpRequest, HttpResponseNotAllowed
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView, ListCreateAPIView, RetrieveAPIView
from sentry_sdk import metrics as sentry_metrics

from codecov_auth.authentication.repo_auth import (
    GitHubOIDCTokenAuthentication,
    GlobalTokenAuthentication,
    OrgLevelTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
    TokenlessAuthentication,
    repo_auth_custom_exception_handler,
)
from reports.models import CommitReport, ReportResults
from services.task import TaskService
from upload.helpers import generate_upload_sentry_metrics_tags
from upload.serializers import CommitReportSerializer, ReportResultsSerializer
from upload.views.base import GetterMixin
from upload.views.uploads import CanDoCoverageUploadsPermission

log = logging.getLogger(__name__)


class ReportViews(ListCreateAPIView, GetterMixin):
    serializer_class = CommitReportSerializer
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

    def perform_create(self, serializer):
        repository = self.get_repo()
        commit = self.get_commit(repository)
        log.info(
            "Request to create new report",
            extra=dict(repo=repository.name, commit=commit.commitid),
        )
        code = serializer.validated_data.get("code")
        if code == "default":
            serializer.validated_data["code"] = None
        instance = serializer.save(
            commit_id=commit.id,
            report_type=CommitReport.ReportType.COVERAGE,
        )
        TaskService().preprocess_upload(
            repository.repoid, commit.commitid, instance.code
        )
        sentry_metrics.incr(
            "upload",
            tags=generate_upload_sentry_metrics_tags(
                action="coverage",
                endpoint="create_report",
                request=self.request,
                repository=repository,
                is_shelter_request=self.is_shelter_request(),
            ),
        )
        return instance

    def list(self, request: HttpRequest, service: str, repo: str, commit_sha: str):
        return HttpResponseNotAllowed(permitted_methods=["POST"])


class ReportResultsView(
    CreateAPIView,
    RetrieveAPIView,
    GetterMixin,
):
    serializer_class = ReportResultsSerializer
    permission_classes = [CanDoCoverageUploadsPermission]
    authentication_classes = [
        GlobalTokenAuthentication,
        OrgLevelTokenAuthentication,
        GitHubOIDCTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
    ]

    def get_exception_handler(self):
        return repo_auth_custom_exception_handler

    def perform_create(self, serializer):
        repository = self.get_repo()
        commit = self.get_commit(repository)
        report = self.get_report(commit)
        instance = ReportResults.objects.filter(report=report).first()
        if not instance:
            instance = serializer.save(
                report=report, state=ReportResults.ReportResultsStates.PENDING
            )
        else:
            instance.state = ReportResults.ReportResultsStates.PENDING
            instance.save()
        TaskService().create_report_results(
            commitid=commit.commitid,
            repoid=repository.repoid,
            report_code=report.code,
        )
        sentry_metrics.incr(
            "upload",
            tags=generate_upload_sentry_metrics_tags(
                action="coverage",
                endpoint="create_report_results",
                request=self.request,
                repository=repository,
                is_shelter_request=self.is_shelter_request(),
            ),
        )
        return instance

    def get_object(self):
        repository = self.get_repo()
        commit = self.get_commit(repository)
        report = self.get_report(commit)
        try:
            report_results = ReportResults.objects.get(report=report)
        except ReportResults.DoesNotExist:
            log.info(
                "Report Results not found",
                extra=dict(
                    commit_sha=commit.commitid,
                    report_code=self.kwargs.get("report_code"),
                ),
            )
            raise ValidationError("Report Results not found")
        return report_results
