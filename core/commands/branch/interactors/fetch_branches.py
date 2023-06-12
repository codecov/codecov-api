from django.db.models import OuterRef, Q, Subquery

from codecov.commands.base import BaseInteractor
from codecov.db import sync_to_async
from core.models import Commit


class FetchRepoBranchesInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, repository, filters):
        queryset = repository.branches.all()

        filters = filters or {}
        search_value = filters.get("search_value")
        if search_value:
            queryset = queryset.filter(name__icontains=search_value)

        merged = filters.get("merged_branches", False)
        if not merged:
            queryset = queryset.annotate(
                merged=Subquery(
                    Commit.objects.filter(
                        commitid=OuterRef("head"),
                        repository_id=OuterRef("repository__repoid"),
                    ).values("merged")[:1]
                )
            ).filter(
                Q(merged__isnot=True)  # exclude merged branches
                | Q(name=repository.branch)  # but always include the default branch
            )

        return queryset
