from asgiref.sync import sync_to_async
from codecov.commands.base import BaseInteractor
from django.db.models import Prefetch

from reports.models import CommitReport

class FetchCommitsInteractor(BaseInteractor):
    def apply_filters_to_commits_queryset(self, queryset, filters):
      filters = filters or {}
      has_uploaded_coverage = filters.get("has_uploaded_coverage")
      if has_uploaded_coverage is False:
        queryset = queryset.exclude(ci_passed__isnull=True)
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