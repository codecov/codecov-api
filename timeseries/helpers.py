import math
from datetime import datetime, timedelta
from typing import Iterable

from django.conf import settings
from django.contrib.postgres.fields.jsonb import KeyTextTransform
from django.db import connections
from django.db.models import Avg, F, FloatField, Max, Min, QuerySet, Sum
from django.db.models.functions import Cast, Trunc
from django.utils import timezone

from codecov_auth.models import Owner
from core.models import Commit, Repository
from reports.models import RepositoryFlag
from services.archive import ReportService
from services.task import TaskService
from timeseries.models import (
    Dataset,
    Interval,
    Measurement,
    MeasurementName,
    MeasurementSummary,
)

interval_deltas = {
    Interval.INTERVAL_1_DAY: timedelta(days=1),
    Interval.INTERVAL_7_DAY: timedelta(days=7),
    Interval.INTERVAL_30_DAY: timedelta(days=30),
}


def save_commit_measurements(commit: Commit) -> None:
    """
    Save the timeseries measurements relevant to a particular commit.
    Currently these are:
      - the report total coverage
      - the flag coverage for each relevant flag
    """
    report_service = ReportService()
    report = report_service.build_report_from_commit(commit)

    if not report:
        return

    repository = commit.repository

    Measurement(
        name=MeasurementName.COVERAGE.value,
        owner_id=repository.author_id,
        repo_id=repository.pk,
        flag_id=None,
        branch=commit.branch,
        commit_sha=commit.commitid,
        timestamp=commit.timestamp,
        value=report.totals.coverage,
    ).upsert()

    for flag_name, flag in report.flags.items():
        repo_flag, created = RepositoryFlag.objects.get_or_create(
            repository_id=repository.pk,
            flag_name=flag_name,
        )

        Measurement(
            name=MeasurementName.FLAG_COVERAGE.value,
            owner_id=repository.author_id,
            repo_id=repository.pk,
            flag_id=repo_flag.pk,
            branch=commit.branch,
            commit_sha=commit.commitid,
            timestamp=commit.timestamp,
            value=flag.totals.coverage,
        ).upsert()


def save_repo_measurements(
    repository: Repository, start_date: datetime, end_date: datetime
) -> None:
    """
    Save the timeseries measurements relevant to a given repository and date range.
    Currently these are:
      - commit measurements for each of the repository's commits in the time range
    """
    coverage_dataset, created = Dataset.objects.get_or_create(
        name=MeasurementName.COVERAGE.value,
        repository_id=repository.pk,
    )
    flag_coverage_dataset, created = Dataset.objects.get_or_create(
        name=MeasurementName.FLAG_COVERAGE.value,
        repository_id=repository.pk,
    )

    commits = repository.commits.filter(
        timestamp__gte=start_date,
        timestamp__lte=end_date,
    )

    for commit in commits.iterator():
        commit.repository = repository
        save_commit_measurements(commit)

    coverage_dataset.backfilled = True
    coverage_dataset.save()
    flag_coverage_dataset.backfilled = True
    flag_coverage_dataset.save()


def refresh_measurement_summaries(start_date: datetime, end_date: datetime) -> None:
    """
    Refresh the measurement summaries for the given time range.
    This calls a TimescaleDB provided SQL function for each of the continuous aggregates
    to refresh the aggregate data in the provided time range.
    """
    continuous_aggregates = [
        "timeseries_measurement_summary_1day",
        "timeseries_measurement_summary_7day",
        "timeseries_measurement_summary_30day",
    ]
    with connections["timeseries"].cursor() as cursor:
        for cagg in continuous_aggregates:
            sql = f"CALL refresh_continuous_aggregate('{cagg}', '{start_date.isoformat()}', '{end_date.isoformat()}')"
            cursor.execute(sql)


def aggregate_measurements(
    queryset: QuerySet, group_by: Iterable[str] = None
) -> QuerySet:
    """
    The given queryset is a set of measurement summaries.  These are already
    pre-aggregated by (timestamp, owner_id, repo_id, flag_id, branch) via TimescaleDB's
    continuous aggregates.  If we want to further aggregate over any of those columns
    then we need to perform additional aggregation in SQL.  That is what this function
    does to the given queryset.
    """
    if not group_by:
        group_by = ["timestamp_bin"]

    return (
        queryset.values(*group_by)
        .annotate(
            min=Min("value_min"),
            max=Max("value_max"),
            avg=(Sum(F("value_avg") * F("value_count")) / Sum("value_count")),
        )
        .order_by("timestamp_bin")
    )


def coverage_measurements(
    interval: Interval,
    start_date: datetime,
    end_date: datetime,
    **filters,
):
    queryset = (
        MeasurementSummary.agg_by(interval)
        .filter(
            name=MeasurementName.COVERAGE.value,
            timestamp_bin__gte=start_date,
            timestamp_bin__lte=end_date,
        )
        .filter(**filters)
    )
    return aggregate_measurements(queryset)


def trigger_backfill(dataset: Dataset):
    """
    Triggers a backfill for the full timespan of the dataset's repo's commits.
    """
    oldest_commit = (
        Commit.objects.filter(repository_id=dataset.repository_id)
        .order_by("timestamp")
        .first()
    )

    newest_commit = (
        Commit.objects.filter(repository_id=dataset.repository_id)
        .order_by("-timestamp")
        .first()
    )

    if oldest_commit and newest_commit:
        # dates to span the entire range of commits
        start_date = oldest_commit.timestamp.date()
        start_date = datetime.fromordinal(start_date.toordinal())
        end_date = newest_commit.timestamp.date() + timedelta(days=1)
        end_date = datetime.fromordinal(end_date.toordinal())

        TaskService().backfill_dataset(
            dataset,
            start_date=start_date,
            end_date=end_date,
        )


def aligned_start_date(interval: Interval, date: datetime) -> datetime:
    """
    Finds the aligned start date for the given timedelta and date.
    TimescaleDB aligns time buckets starting on 2000-01-03 so this function will
    return the date of the start of the bin containing the given `date`.
    The return value will be <= the given date.
    """
    delta = interval_deltas[interval]

    # TimescaleDB aligns time buckets starting on 2000-01-03)
    aligning_date = datetime(2000, 1, 3, tzinfo=timezone.utc)

    # number of full intervals between aligning date and the requested `after` date
    intervals_before = math.floor((date - aligning_date) / delta)

    # date of time bucket that contains given start date
    return aligning_date + (intervals_before * delta)


def fill_sparse_measurements(
    measurements: Iterable[dict],
    interval: Interval,
    start_date: datetime,
    end_date: datetime,
) -> Iterable[dict]:
    """
    Fill in sparse array of measurements with values such that we
    have an entry for every interval within the requested time range.
    Those placeholder entries will have empty measurement values.
    """
    by_timestamp = {
        measurement["timestamp_bin"].replace(tzinfo=timezone.utc): measurement
        for measurement in measurements
    }

    delta = interval_deltas[interval]
    start_date = aligned_start_date(interval, start_date)

    intervals = []

    current_date = start_date
    while current_date <= end_date:
        if current_date in by_timestamp:
            intervals.append(by_timestamp[current_date])
        else:
            # interval not found
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


def coverage_fallback_query(
    interval: Interval,
    start_date: datetime,
    end_date: datetime,
    **filters,
):
    """
    Query for coverage timeseries directly from the database
    """
    intervals = {
        Interval.INTERVAL_1_DAY: "day",
        Interval.INTERVAL_7_DAY: "week",
        Interval.INTERVAL_30_DAY: "month",
    }

    return (
        Commit.objects.filter(
            timestamp__gte=start_date,
            timestamp__lte=end_date,
        )
        .filter(**filters)
        .annotate(
            timestamp_bin=Trunc("timestamp", intervals[interval], tzinfo=timezone.utc),
            coverage=Cast(KeyTextTransform("c", "totals"), output_field=FloatField()),
        )
        .filter(coverage__isnull=False)
        .values("timestamp_bin")
        .annotate(
            min=Min("coverage"),
            max=Max("coverage"),
            avg=Avg("coverage"),
        )
        .order_by("timestamp_bin")
    )


def repository_coverage_measurements_with_fallback(
    repository: Repository,
    interval: Interval,
    start_date: datetime,
    end_date: datetime,
    branch: str = None,
):
    """
    Tries to return repository coverage measurements from Timescale.
    If those are not available then we trigger a backfill and return computed results
    directly from the primary database (much slower to query).
    """
    dataset = None
    if settings.TIMESERIES_ENABLED:
        dataset = Dataset.objects.filter(
            name=MeasurementName.COVERAGE.value,
            repository_id=repository.pk,
        ).first()

    if settings.TIMESERIES_ENABLED and dataset and dataset.is_backfilled():
        # timeseries data is ready
        return coverage_measurements(
            interval,
            start_date,
            end_date,
            owner_id=repository.author_id,
            repo_id=repository.pk,
            branch=branch or repository.branch,
        )
    else:
        if settings.TIMESERIES_ENABLED and not dataset:
            # we need to backfill
            dataset = Dataset.objects.create(
                name=MeasurementName.COVERAGE.value,
                repository_id=repository.pk,
            )
            trigger_backfill(dataset)

        # we're still backfilling or timeseries is disabled
        return coverage_fallback_query(
            interval,
            start_date,
            end_date,
            repository_id=repository.pk,
            branch=branch or repository.branch,
        )


def owner_coverage_measurements_with_fallback(
    owner: Owner,
    repo_ids: Iterable[str],
    interval: Interval,
    start_date: datetime,
    end_date: datetime,
):
    """
    Tries to return owner coverage measurements from Timescale.
    If those are not available then we trigger a backfill and return computed results
    directly from the primary database (much slower to query).
    """
    datasets = []
    if settings.TIMESERIES_ENABLED:
        datasets = Dataset.objects.filter(
            name=MeasurementName.COVERAGE.value,
            repository_id__in=repo_ids,
        )

    all_backfilled = len(datasets) == len(repo_ids) and all(
        dataset.is_backfilled() for dataset in datasets
    )

    if settings.TIMESERIES_ENABLED and all_backfilled:
        # timeseries data is ready
        return coverage_measurements(
            interval,
            start_date,
            end_date,
            owner_id=owner.pk,
            repo_id__in=repo_ids,
        )
    else:
        if settings.TIMESERIES_ENABLED:
            # we need to backfill some datasets
            dataset_repo_ids = set(dataset.repository_id for dataset in datasets)
            missing_dataset_repo_ids = set(repo_ids) - dataset_repo_ids
            created_datasets = Dataset.objects.bulk_create(
                [
                    Dataset(name=MeasurementName.COVERAGE.value, repository_id=repo_id)
                    for repo_id in missing_dataset_repo_ids
                ]
            )
            for dataset in created_datasets:
                trigger_backfill(dataset)

        # we're still backfilling or timeseries is disabled
        return coverage_fallback_query(
            interval,
            start_date,
            end_date,
            repository_id__in=repo_ids,
        )
