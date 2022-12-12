import logging

from rest_framework.exceptions import ValidationError

from codecov_auth.models import Service
from core.models import Commit, Repository
from reports.models import CommitReport
from upload.views.helpers import get_repository_from_string

log = logging.getLogger(__name__)


class GetterMixin:
    def get_repo(self) -> Repository:
        service = self.kwargs.get("service")
        repo_slug = self.kwargs.get("repo")
        try:
            service_enum = Service(service)
        except ValueError:
            log.info(f"Service not found: {service}", extra=dict(repo_slug=repo_slug))
            raise ValidationError(f"Service not found: {service}")

        repository = get_repository_from_string(service_enum, repo_slug)

        if not repository:
            log.info(
                "Repository not found",
                extra=dict(repo_slug=repo_slug),
            )
            raise ValidationError(f"Repository not found")
        return repository

    def get_commit(self, repo: Repository) -> Commit:
        commit_sha = self.kwargs.get("commit_sha")
        try:
            commit = Commit.objects.get(
                commitid=commit_sha, repository__repoid=repo.repoid
            )
            return commit
        except Commit.DoesNotExist:
            log.info(
                "Commit SHA not found",
                extra=dict(repo=repo.name, commit_sha=commit_sha),
            )
            raise ValidationError("Commit SHA not found")

    def get_report(self, commit: Commit) -> CommitReport:
        report_code = self.kwargs.get("report_code")
        if report_code == "default":
            report_code = None
        try:
            report = CommitReport.objects.get(code=report_code, commit=commit)
            return report
        except CommitReport.DoesNotExist:
            log.info(
                "Report not found",
                extra=dict(commit_sha=commit.commitid, report_code=report_code),
            )
            raise ValidationError(f"Report not found")
