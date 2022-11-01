from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor


class FetchRepoBranchesInteractor(BaseInteractor):
    def apply_filters_to_branches_queryset(self, queryset, filters):
        filters = filters or {}
        search_value = filters.get("search_value")
        if search_value:
            queryset = queryset.filter(name__contains=search_value)
        return queryset

    @sync_to_async
    def execute(self, repository, filters):
        queryset = repository.branches.all()
        return self.apply_filters_to_branches_queryset(queryset, filters)
