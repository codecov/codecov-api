from datetime import datetime
from typing import Iterable, Mapping

from django.db.models import QuerySet

from compare.models import CommitComparison, FlagComparison
from core.models import Repository
from graphql_api.actions.measurements import measurements_by_ids
from reports.models import RepositoryFlag
from timeseries.models import Interval, MeasurementName


def flags_for_repo(repository: Repository, filters: Mapping = {}) -> QuerySet:
    queryset = RepositoryFlag.objects.filter(
        repository=repository,
        deleted__isnot=True,
    )
    queryset = _apply_filters(queryset, filters or {})
    return queryset


def _apply_filters(queryset: QuerySet, filters: Mapping) -> QuerySet:
    term = filters.get("term")
    flags_names = filters.get("flags_names")
    if flags_names:
        queryset = queryset.filter(flag_name__in=flags_names)
    if term:
        queryset = queryset.filter(flag_name__contains=term)

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


def flag_measurements(
    repository: Repository,
    flag_ids: Iterable[int],
    interval: Interval,
    after: datetime,
    before: datetime,
) -> Mapping[int, Iterable[dict]]:
    measurements = measurements_by_ids(
        repository=repository,
        measurable_name=MeasurementName.FLAG_COVERAGE.value,
        measurable_ids=[str(flag_id) for flag_id in flag_ids],
        interval=interval,
        after=after,
        before=before,
    )

    # By default the measurable_id is str type,
    # however for flags we need to convert it to an int
    return {
        int(measurable_id): measurement
        for (measurable_id, measurement) in measurements.items()
    }
