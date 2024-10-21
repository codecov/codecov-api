from typing import Any

from django.db.models import OuterRef, Q, QuerySet, Subquery
from shared.django_apps.core.models import Repository

from codecov.commands.base import BaseInteractor
from codecov.db import sync_to_async
from core.models import Commit


class FetchRepoBranchesInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, repository: Repository, filters: dict[str, Any]) -> QuerySet:
        queryset = repository.branches.all()

        filters = filters or {}
        search_value = filters.get("search_value")
        if search_value:
            # force use of ILIKE to optimize search; django icontains doesn't work
            # see https://github.com/codecov/engineering-team/issues/2537
            queryset = queryset.extra(
                where=['"branches"."branch" ILIKE %s'], params=[f"%{search_value}%"]
            )

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
