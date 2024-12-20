import polars as pl
from django.conf import settings
from shared.api_archive.storage import StorageService
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
        storage_service = StorageService()
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

    return table
