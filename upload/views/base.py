from rest_framework.exceptions import ValidationError

from codecov_auth.models import Service
from core.models import Commit, Repository
from reports.models import CommitReport
from upload.views.helpers import get_repository_from_string


class GetterMixin:
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

    def get_commit(self, repo: Repository) -> Commit:
        commit_sha = self.kwargs.get("commit_sha")
        try:
            commit = Commit.objects.get(
                commitid=commit_sha, repository__repoid=repo.repoid
            )
            return commit
        except Commit.DoesNotExist:
            raise ValidationError("Commit SHA not found")

    def get_report(self, commit: Commit) -> CommitReport:
        report_code = self.kwargs.get("report_code")
        try:
            report = CommitReport.objects.get(code=report_code, commit=commit)
            return report
        except CommitReport.DoesNotExist:
            raise ValidationError(f"Report not found")
