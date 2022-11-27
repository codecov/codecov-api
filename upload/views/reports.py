import logging

from django.http import HttpRequest, HttpResponseNotAllowed, HttpResponseNotFound
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView, ListCreateAPIView
from rest_framework.permissions import AllowAny

from codecov_auth.authentication.repo_auth import (
    GlobalTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
)
from codecov_auth.models import Service
from core.models import Commit, Repository
from reports.models import CommitReport
from upload.serializers import CommitReportSerializer, ReportResultsSerializer
from upload.views.helpers import get_repository_from_string
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


class ReportResultsView(CreateAPIView):
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

    def get_repo(self) -> Repository:
        service = self.kwargs.get("service")
        try:
            service_enum = Service(service)
        except ValueError:
            raise ValidationError(f"Service not found: {service}")

        repo_slug = self.kwargs.get("repo")
        repository = get_repository_from_string(service_enum, repo_slug)

        if not repository:
            raise ValidationError(f"Repository not found")
        return repository

    def get_report(self, commit: Commit) -> CommitReport:
        report_code = self.kwargs.get("report_code")
        try:
            report = CommitReport.objects.get(code=report_code, commit=commit)
            return report
        except CommitReport.DoesNotExist:
            raise ValidationError(f"Report not found")

    def get_commit(self, repo: Repository) -> Commit:
        commit_sha = self.kwargs.get("commit_sha")
        try:
            commit = Commit.objects.get(
                commitid=commit_sha, repository__repoid=repo.repoid
            )
            return commit
        except Commit.DoesNotExist:
            raise ValidationError("Commit SHA not found")
