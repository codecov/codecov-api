from typing import Mapping

from django.db.models import QuerySet

from core.models import Repository
from reports.models import RepositoryFlag


def flags_for_repo(repository: Repository, filters: Mapping = None) -> QuerySet:
    queryset = RepositoryFlag.objects.filter(
        repository=repository,
    )
    queryset = _apply_filters(queryset, filters or {})
    return queryset


def _apply_filters(queryset: QuerySet, filters: Mapping) -> QuerySet:
    term = filters.get("term")
    if term:
        queryset = queryset.filter(flag_name__contains=term)

    return queryset
