import math
from datetime import datetime, timedelta
from time import time
from typing import Iterable, Mapping, Tuple

from django.db.models import Avg, Max, Min, QuerySet
from django.utils import timezone

from compare.models import CommitComparison, FlagComparison
from core.models import Repository
from reports.models import RepositoryFlag
from timeseries.models import Interval, Measurement, MeasurementName, MeasurementSummary


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


def get_flag_comparisons(
    commit_comparison: CommitComparison,
) -> Iterable[FlagComparison]:
    queryset = (
        FlagComparison.objects.select_related("repositoryflag")
        .filter(commit_comparison=commit_comparison.id)
        .all()
    )
    return queryset


interval_deltas = {
    Interval.INTERVAL_1_DAY: timedelta(days=1),
    Interval.INTERVAL_7_DAY: timedelta(days=7),
    Interval.INTERVAL_30_DAY: timedelta(days=30),
}


def _aligned_start_date(delta: timedelta, date: datetime) -> datetime:
    """
    Finds the aligned start date for the given timedelta and date.
    TimescaleDB aligns time buckets starting on 2000-01-03 so this function will
    return the date of the start of the bin containing the given `date`.
    The return value will be <= the given date.
    """
    # TimescaleDB aligns time buckets starting on 2000-01-03)
    aligning_date = datetime(2000, 1, 3, tzinfo=timezone.utc)

    # number of full intervals between aligning date and the requested `after` date
    intervals_before = math.floor((date - aligning_date) / delta)

    # date of time bucket that contains given start date
    return aligning_date + (intervals_before * delta)


def fill_empty_measurements(
    measurements: Iterable[dict],
    interval: Interval,
    after: datetime,
    before: datetime,
) -> Iterable[dict]:
    """
    Fill in sparse array of measurements with empty values such that we
    have an item for every interval within the given time range.
    """
    by_timestamp = {
        measurement["timestamp_bin"]: measurement for measurement in measurements
    }

    delta = interval_deltas[interval]
    start_date = _aligned_start_date(delta, after)
    end_date = before

    intervals = []

    current_date = start_date
    while current_date <= end_date:
        if current_date in by_timestamp:
            intervals.append(by_timestamp[current_date])
        else:
            # empty interval
            intervals.append(
                {
                    "timestamp_bin": current_date,
                    "avg": None,
                    "min": None,
                    "max": None,
                }
            )
        current_date += delta

    return intervals


def flag_measurements(
    repository: Repository,
    flag_ids: Iterable[int],
    interval: Interval,
    after: datetime,
    before: datetime,
) -> Mapping[int, Iterable[dict]]:
    delta = interval_deltas[interval]
    queryset = (
        MeasurementSummary.agg_by(interval)
        .filter(
            name=MeasurementName.FLAG_COVERAGE.value,
            owner_id=repository.author_id,
            repo_id=repository.pk,
            flag_id__in=flag_ids,
            timestamp_bin__gte=_aligned_start_date(delta, after),
            timestamp_bin__lte=before,
        )
        .values("timestamp_bin", "owner_id", "repo_id", "flag_id")
        .annotate(
            avg=Avg("value_avg"),
            min=Min("value_min"),
            max=Max("value_max"),
        )
        .order_by("timestamp_bin")
    )

    # group by flag_id
    measurements = {}
    for measurement in queryset:
        flag_id = measurement["flag_id"]
        if flag_id not in measurements:
            measurements[flag_id] = []
        measurements[flag_id].append(measurement)

    return measurements
