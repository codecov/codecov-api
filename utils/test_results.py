import polars as pl
from shared.storage.exceptions import FileNotInStorageError

from services.redis_configuration import get_redis_connection
from services.storage import StorageService


def get_redis_key(
    repoid: int,
    branch: str,
    interval_start: int,
    interval_end: int | None = None,
) -> str:
    if interval_end is None:
        return f"test_results:{repoid}:{branch}:{interval_start}"
    else:
        return f"test_results:{repoid}:{branch}:{interval_start}:{interval_end}"


def get_storage_key(
    repoid: int, branch: str, interval_start: int, interval_end: int | None = None
) -> str:
    if interval_end is None:
        return f"test_results/rollups/{repoid}/{branch}/{interval_start}"
    else:
        return f"test_results/rollups/{repoid}/{branch}/{interval_start}_{interval_end}"


def get_results(
    repoid: int,
    branch: str,
    interval_start: int,
    interval_end: int | None = None,
) -> pl.DataFrame | None:
    serialized_table = None

    redis_conn = get_redis_connection()
    redis_key = get_redis_key(repoid, branch, interval_start, interval_end)

    redis_result = redis_conn.get(redis_key)

    if redis_result is not None:
        serialized_table = redis_result

    if serialized_table is None:
        storage_service = StorageService()
        storage_key = get_storage_key(repoid, branch, interval_start, interval_end)

        try:
            serialized_table = storage_service.read_file(
                bucket_name="codecov", path=storage_key
            )
        except FileNotInStorageError as e:
            if interval_end is not None:
                return None
            else:
                raise FileNotFoundError(f"File not found in archive: {e}")

    if serialized_table is None:
        return None

    table = pl.read_ipc(serialized_table)

    return table
