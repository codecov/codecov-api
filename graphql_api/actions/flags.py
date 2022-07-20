from typing import Iterable, Mapping

from django.db.models import QuerySet

from compare.models import CommitComparison, FlagComparison
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
    flagsNames = filters.get("flagsNames")
    if term:
        queryset = queryset.filter(flag_name__contains=term)
    if flagsNames and len(flagsNames):
        queryset = queryset.filter(flag_name__in=flagsNames)

    return queryset


def get_flag_comparisons(
    commit_comparison: CommitComparison,
) -> Iterable[FlagComparison]:
    queryset = (
        FlagComparison.objects.select_related("repositoryflag")
        .filter(commit_comparison=commit_comparison.id)
        .all()
    )
    return queryset
