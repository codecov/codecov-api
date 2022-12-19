import logging

from django.http import HttpRequest, HttpResponseNotAllowed, HttpResponseNotFound
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView, ListCreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from codecov_auth.authentication.repo_auth import (
    GlobalTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
)
from reports.models import ReportResults
from upload.serializers import CommitReportSerializer, ReportResultsSerializer
from upload.views.base import GetterMixin
from upload.views.uploads import CanDoCoverageUploadsPermission

log = logging.getLogger(__name__)


class ReportViews(ListCreateAPIView):
    serializer_class = CommitReportSerializer
    permission_classes = [
        # TODO: Implement the correct permissions
        AllowAny,
    ]

    def create(self, request: HttpRequest, service: str, repo: str, commit_sha: str):
        log.info(
            "Request to create new report", extra=dict(repo=repo, commit_id=commit_sha)
        )
        return HttpResponseNotFound("Not available")

    def list(self, request: HttpRequest, service: str, repo: str, commit_sha: str):
        return HttpResponseNotAllowed(permitted_methods=["POST"])


class ReportResultsView(
    ListCreateAPIView,
    GetterMixin,
):
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

    def get(self, request, *args, **kwargs):
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
            raise ValidationError(f"Report Results not found")
        serializer = self.get_serializer(report_results)
        return Response(serializer.data)
