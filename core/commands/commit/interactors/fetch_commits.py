from asgiref.sync import sync_to_async
from django.db.models import Prefetch

from codecov.commands.base import BaseInteractor
from reports.models import CommitReport


class FetchCommitsInteractor(BaseInteractor):
    def apply_filters_to_commits_queryset(self, queryset, filters):
        filters = filters or {}
        hide_failed_ci = filters.get("hide_failed_ci")
        branch_name = filters.get("branch_name")
        if hide_failed_ci is True:
            queryset = queryset.filter(ci_passed=True)
        if branch_name:
            queryset = queryset.filter(branch=branch_name)
        return queryset

    @sync_to_async
    def execute(self, repository, filters):
        # prefetch the CommitReport with the ReportLevelTotals
        prefetch = Prefetch(
            "reports", queryset=CommitReport.objects.select_related("reportleveltotals")
        )
        queryset = repository.commits.prefetch_related(prefetch).all()
        queryset = self.apply_filters_to_commits_queryset(queryset, filters)
        return queryset
