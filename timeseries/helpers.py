from datetime import datetime

from django.db import connections

from core.models import Commit, Repository
from reports.models import RepositoryFlag
from timeseries.models import Measurement, MeasurementName


def save_commit_measurements(commit: Commit) -> None:
    """
    Save the timeseries measurements relevant to a particular commit.
    Currently these are:
      - the report total coverage
      - the flag coverage for each relevant flag
    """
    report = commit.full_report

    Measurement(
        name=MeasurementName.COVERAGE.value,
        owner_id=commit.author_id,
        repo_id=commit.repository_id,
        flag_id=None,
        branch=commit.branch,
        commit_sha=commit.commitid,
        timestamp=commit.timestamp,
        value=report.totals.coverage,
    ).upsert()

    for flag_name, flag in report.flags.items():
        repo_flag = commit.repository.flags.filter(flag_name=flag_name).first()
        if repo_flag is None:
            repo_flag = RepositoryFlag.objects.create(
                repository_id=commit.repository_id,
                flag_name=flag_name,
            )

        Measurement(
            name=MeasurementName.FLAG_COVERAGE.value,
            owner_id=commit.author_id,
            repo_id=commit.repository_id,
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
      - commit measurements each of the repository's commits in the time range
    """
    commits = repository.commits.filter(
        timestamp__gte=start_date,
        timestamp__lte=end_date,
    )

    for commit in commits.iterator():
        commit.repository = repository
        save_commit_measurements(commit)


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
