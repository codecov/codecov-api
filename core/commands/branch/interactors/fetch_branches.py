from codecov.commands.base import BaseInteractor
from codecov.db import sync_to_async


class FetchRepoBranchesInteractor(BaseInteractor):
    def apply_filters_to_branches_queryset(self, queryset, filters):
        filters = filters or {}
        search_value = filters.get("search_value")
        if search_value:
            queryset = queryset.filter(name__icontains=search_value)
        return queryset

    @sync_to_async
    def execute(self, repository, filters):
        queryset = repository.branches.all()
        return self.apply_filters_to_branches_queryset(queryset, filters)
