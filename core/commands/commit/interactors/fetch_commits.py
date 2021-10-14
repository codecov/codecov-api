from asgiref.sync import sync_to_async
from codecov.commands.base import BaseInteractor

class FetchCommitsInteractor(BaseInteractor):
    def apply_filters_to_commits_queryset(self, queryset, filters):
      filters = filters or {}
      has_uploaded_coverage = filters.get("has_uploaded_coverage")
      if not has_uploaded_coverage:
        queryset = queryset.exclude(report__isnull=True)
      return queryset

    @sync_to_async
    def execute(self, repository, filters):
        queryset = repository.commits.all()
        queryset = self.apply_filters_to_commits_queryset(queryset, filters)
        return queryset