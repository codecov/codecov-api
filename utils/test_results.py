import tempfile
from datetime import date, timedelta

import polars as pl
from django.conf import settings
from shared.helpers.redis import get_redis_connection
from shared.metrics import Summary
from shared.storage import get_appropriate_storage_service
from shared.storage.exceptions import FileNotInStorageError

from rollouts import READ_NEW_TA
from services.task import TaskService

get_results_summary = Summary(
    "test_results_get_results", "Time it takes to download results from GCS", ["impl"]
)


def redis_key(
    repoid: int,
    branch: str,
    interval_start: int,
    interval_end: int | None = None,
) -> str:
    key = f"test_results:{repoid}:{branch}:{interval_start}"

    if interval_end is not None:
        key = f"{key}:{interval_end}"

    return key


def storage_key(
    repoid: int, branch: str, interval_start: int, interval_end: int | None = None
) -> str:
    key = f"test_results/rollups/{repoid}/{branch}/{interval_start}"

    if interval_end is not None:
        key = f"{key}_{interval_end}"

    return key


def dedup_table(table: pl.DataFrame) -> pl.DataFrame:
    failure_rate_expr = (
        pl.col("failure_rate")
        * (pl.col("total_fail_count") + pl.col("total_pass_count"))
    ).sum() / (pl.col("total_fail_count") + pl.col("total_pass_count")).sum()

    flake_rate_expr = (
        pl.col("flake_rate") * (pl.col("total_fail_count") + pl.col("total_pass_count"))
    ).sum() / (pl.col("total_fail_count") + pl.col("total_pass_count")).sum()

    avg_duration_expr = (
        pl.col("avg_duration")
        * (pl.col("total_pass_count") + pl.col("total_fail_count"))
    ).sum() / (pl.col("total_pass_count") + pl.col("total_fail_count")).sum()

    # dedup
    table = (
        table.group_by("name")
        .agg(
            pl.col("testsuite").alias("testsuite"),
            pl.col("flags").explode().unique().alias("flags"),
            failure_rate_expr.fill_nan(0).alias("failure_rate"),
            flake_rate_expr.fill_nan(0).alias("flake_rate"),
            pl.col("updated_at").max().alias("updated_at"),
            avg_duration_expr.fill_nan(0).alias("avg_duration"),
            pl.col("total_fail_count").sum().alias("total_fail_count"),
            pl.col("total_flaky_fail_count").sum().alias("total_flaky_fail_count"),
            pl.col("total_pass_count").sum().alias("total_pass_count"),
            pl.col("total_skip_count").sum().alias("total_skip_count"),
            pl.col("commits_where_fail")
            .sum()
            .alias("commits_where_fail"),  # TODO: this is wrong
            pl.col("last_duration").max().alias("last_duration"),
        )
        .sort("name")
    )

    return table


def get_results(
    repoid: int,
    branch: str,
    interval_start: int,
    interval_end: int | None = None,
) -> pl.DataFrame | None:
    """
    try redis
    if redis is empty
        try storage
        if storage is empty
            return None
        else
            cache to redis
    deserialize
    """
    # try redis
    if READ_NEW_TA.check_value(repoid):
        func = new_get_results
        label = "new"
    else:
        func = old_get_results
        label = "old"

    with get_results_summary.labels(label).time():
        return func(repoid, branch, interval_start, interval_end)


def old_get_results(
    repoid: int,
    branch: str,
    interval_start: int,
    interval_end: int | None = None,
) -> pl.DataFrame | None:
    redis_conn = get_redis_connection()
    key = redis_key(repoid, branch, interval_start, interval_end)
    result: bytes | None = redis_conn.get(key)

    if result is None:
        # try storage
        storage_service = get_appropriate_storage_service(repoid)
        key = storage_key(repoid, branch, interval_start, interval_end)
        try:
            result = storage_service.read_file(
                bucket_name=settings.GCS_BUCKET_NAME, path=key
            )
            # cache to redis
            TaskService().cache_test_results_redis(repoid, branch)
        except FileNotInStorageError:
            # give up
            return None

    # deserialize
    table = pl.read_ipc(result)

    if table.height == 0:
        return None

    table = dedup_table(table)

    return table


def rollup_blob_path(repoid: int, branch: str | None = None) -> str:
    return (
        f"test_analytics/branch_rollups/{repoid}/{branch}.arrow"
        if branch
        else f"test_analytics/repo_rollups/{repoid}.arrow"
    )


def no_version_agg_table(table: pl.LazyFrame) -> pl.LazyFrame:
    failure_rate_expr = (pl.col("fail_count")).sum() / (
        pl.col("fail_count") + pl.col("pass_count")
    ).sum()

    flake_rate_expr = (pl.col("flaky_fail_count")).sum() / (
        pl.col("fail_count") + pl.col("pass_count")
    ).sum()

    avg_duration_expr = (
        pl.col("avg_duration") * (pl.col("pass_count") + pl.col("fail_count"))
    ).sum() / (pl.col("pass_count") + pl.col("fail_count")).sum()

    table = table.group_by(pl.col("computed_name").alias("name")).agg(
        pl.col("flags")
        .explode()
        .unique()
        .alias("flags"),  # TODO: filter by this before we aggregate
        pl.col("failing_commits").sum().alias("commits_where_fail"),
        pl.col("last_duration").max().alias("last_duration"),
        failure_rate_expr.alias("failure_rate"),
        flake_rate_expr.alias("flake_rate"),
        avg_duration_expr.alias("avg_duration"),
        pl.col("pass_count").sum().alias("total_pass_count"),
        pl.col("fail_count").sum().alias("total_fail_count"),
        pl.col("flaky_fail_count").sum().alias("total_flaky_fail_count"),
        pl.col("skip_count").sum().alias("total_skip_count"),
        pl.col("updated_at").max().alias("updated_at"),
    )

    return table


def v1_agg_table(table: pl.LazyFrame) -> pl.LazyFrame:
    failure_rate_expr = (pl.col("fail_count")).sum() / (
        pl.col("fail_count") + pl.col("pass_count")
    ).sum()

    flake_rate_expr = (pl.col("flaky_fail_count")).sum() / (
        pl.col("fail_count") + pl.col("pass_count")
    ).sum()

    avg_duration_expr = (
        pl.col("avg_duration") * (pl.col("pass_count") + pl.col("fail_count"))
    ).sum() / (pl.col("pass_count") + pl.col("fail_count")).sum()

    table = table.group_by("computed_name").agg(
        pl.col("testsuite").alias(
            "testsuite"
        ),  # TODO: filter by this before we aggregate
        pl.col("flags")
        .explode()
        .unique()
        .alias("flags"),  # TODO: filter by this before we aggregate
        pl.col("failing_commits").sum().alias("commits_where_fail"),
        pl.col("last_duration").max().alias("last_duration"),
        failure_rate_expr.alias("failure_rate"),
        flake_rate_expr.alias("flake_rate"),
        avg_duration_expr.alias("avg_duration"),
        pl.col("pass_count").sum().alias("total_pass_count"),
        pl.col("fail_count").sum().alias("total_fail_count"),
        pl.col("flaky_fail_count").sum().alias("total_flaky_fail_count"),
        pl.col("skip_count").sum().alias("total_skip_count"),
        pl.col("updated_at").max().alias("updated_at"),
    )

    return table


def new_get_results(
    repoid: int,
    branch: str | None,
    interval_start: int,
    interval_end: int | None = None,
) -> pl.DataFrame | None:
    storage_service = get_appropriate_storage_service(repoid)
    key = rollup_blob_path(repoid, branch)
    try:
        with tempfile.TemporaryFile() as tmp:
            metadata = {}
            storage_service.read_file(
                bucket_name=settings.GCS_BUCKET_NAME,
                path=key,
                file_obj=tmp,
                metadata_container=metadata,
            )

            table = pl.scan_ipc(tmp)

            # filter start
            start_date = date.today() - timedelta(days=interval_start)
            table = table.filter(pl.col("timestamp_bin") >= start_date)

            # filter end
            if interval_end is not None:
                end_date = date.today() - timedelta(days=interval_end)
                table = table.filter(pl.col("timestamp_bin") <= end_date)

            # aggregate
            match metadata.get("version"):
                case "1":
                    table = v1_agg_table(table)
                case _:  # no version is missding
                    table = no_version_agg_table(table)

            return table.collect()
    except FileNotInStorageError:
        return None
