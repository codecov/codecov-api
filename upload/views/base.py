import logging
from typing import Optional

from django.conf import settings
from rest_framework.exceptions import ValidationError

from codecov_auth.models import Service
from core.models import Commit, Repository
from reports.models import CommitReport
from upload.views.helpers import get_repository_from_string

log = logging.getLogger(__name__)


class ShelterMixin:
    def is_shelter_request(self) -> bool:
        """
        Returns true when the incoming request originated from a Shelter.
        Shelter adds an `X-Shelter-Token` header which contains a shared secret.
        Use of that shared secret allows certain priviledged functionality that normal
        uploads cannot access.
        """
        shelter_token = self.request.META.get("HTTP_X_SHELTER_TOKEN")
        return shelter_token and shelter_token == settings.SHELTER_SHARED_SECRET


class GetterMixin(ShelterMixin):
    def get_repo(self) -> Repository:
        service = self.kwargs.get("service")
        repo_slug = self.kwargs.get("repo")
        try:
            service_enum = Service(service)
        except ValueError:
            log.warning(
                f"Service not found: {service}", extra=dict(repo_slug=repo_slug)
            )
            raise ValidationError(f"Service not found: {service}")

        repository = get_repository_from_string(service_enum, repo_slug)

        if not repository:
            log.warning(
                "Repository not found",
                extra=dict(repo_slug=repo_slug),
            )
            raise ValidationError("Repository not found")
        return repository

    def get_commit(self, repo: Repository) -> Commit:
        commit_sha = self.kwargs.get("commit_sha")
        try:
            commit = Commit.objects.get(
                commitid=commit_sha, repository__repoid=repo.repoid
            )
            return commit
        except Commit.DoesNotExist:
            log.warning(
                "Commit SHA not found",
                extra=dict(repo=repo.name, commit_sha=commit_sha),
            )
            raise ValidationError("Commit SHA not found")

    def get_report(
        self,
        commit: Commit,
        report_type: Optional[
            CommitReport.ReportType
        ] = CommitReport.ReportType.COVERAGE,
    ) -> CommitReport:
        report_code = self.kwargs.get("report_code")
        if report_code == "default":
            report_code = None
        queryset = CommitReport.objects.filter(code=report_code, commit=commit)
        if report_type == CommitReport.ReportType.COVERAGE:
            queryset = queryset.coverage_reports()
        else:
            queryset = queryset.filter(report_type=report_type)
        report = queryset.first()
        if report is None:
            log.warning(
                "Report not found",
                extra=dict(commit_sha=commit.commitid, report_code=report_code),
            )
            raise ValidationError("Report not found")
        if report.report_type is None:
            report.report_type = CommitReport.ReportType.COVERAGE
            report.save()
        return report
