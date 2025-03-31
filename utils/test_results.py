import polars as pl
from django.conf import settings
from shared.storage import get_appropriate_storage_service
from shared.storage.exceptions import FileNotInStorageError

from services.redis_configuration import get_redis_connection
from services.task import TaskService


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
            pl.col("commits_where_fail").sum().alias("commits_where_fail"),
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
