from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor


class FetchPullRequestsInteractor(BaseInteractor):
    def apply_filters_to_pulls_queryset(self, queryset, filters):
        filters = filters or {}
        state = filters.get("state")
        if state:
            queryset = queryset.filter(state=state.value)
        return queryset

    @sync_to_async
    def execute(self, repository, filters):
        queryset = repository.pull_requests.all()
        queryset = self.apply_filters_to_pulls_queryset(queryset, filters)
        return queryset
