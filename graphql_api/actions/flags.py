from datetime import datetime
from functools import lru_cache
from typing import Iterable, Mapping

from django.db.models import Avg, Max, Min, QuerySet

from compare.models import CommitComparison, FlagComparison
from core.models import Repository
from reports.models import RepositoryFlag
from timeseries.helpers import aggregate_measurements, aligned_start_date
from timeseries.models import Interval, MeasurementName, MeasurementSummary


def flags_for_repo(repository: Repository, filters: Mapping = None) -> QuerySet:
    queryset = RepositoryFlag.objects.filter(
        repository=repository,
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


@lru_cache
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
    queryset = MeasurementSummary.agg_by(interval).filter(
        name=MeasurementName.FLAG_COVERAGE.value,
        owner_id=repository.author_id,
        repo_id=repository.pk,
        flag_id__in=flag_ids,
        timestamp_bin__gte=aligned_start_date(interval, after),
        timestamp_bin__lte=before,
    )

    queryset = aggregate_measurements(
        queryset, ["timestamp_bin", "owner_id", "repo_id", "flag_id"]
    )

    # group by flag_id
    measurements = {}
    for measurement in queryset:
        flag_id = measurement["flag_id"]
        if flag_id not in measurements:
            measurements[flag_id] = []
        measurements[flag_id].append(measurement)

    return measurements
