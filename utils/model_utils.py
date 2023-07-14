import json
import logging
from functools import lru_cache
from typing import Any, Callable

from shared.storage.exceptions import FileNotInStorageError

from core.models import Repository
from services.archive import ArchiveService

log = logging.getLogger(__name__)


class ArchiveFieldInterfaceMeta(type):
    def __subclasscheck__(cls, subclass):
        return (
            hasattr(subclass, "get_repository")
            and callable(subclass.get_repository)
            and hasattr(subclass, "get_commitid")
            and callable(subclass.get_commitid)
            and hasattr(subclass, "should_write_to_storage")
            and callable(subclass.should_write_to_storage)
        )


class ArchiveFieldInterface(metaclass=ArchiveFieldInterfaceMeta):
    """Any class that uses ArchiveField must implement this interface"""

    def get_repository(self) -> Repository:
        raise NotImplementedError()

    def get_commitid(self) -> str:
        raise NotImplementedError()


class ArchiveField:
    """This is a helper class that transparently handles models' fields that are saved in storage.
    Classes that use the ArchiveField MUST implement ArchiveFieldInterface. It ill throw an error otherwise.
    It uses the Descriptor pattern: https://docs.python.org/3/howto/descriptor.html

    Arguments:
        should_write_to_storage_fn: Callable function that decides if data should be written to storage.
        It should take 1 argument: the object instance.

        rehydrate_fn: Callable function to allow you to decode your saved data into internal representations.
        The default value does nothing.
        Data retrieved both from DB and storage pass through this function to guarantee consistency.
        It should take 2 arguments: the object instance and the encoded data.

        default_value: Any value that will be returned if we can't save the data for whatever reason

    Example:
        archive_field = ArchiveField(
            should_write_to_storage_fn=should_write_data,
            rehydrate_fn=rehidrate_data,
            default_value='default'
        )
    For a full example check utils/tests/unit/test_model_utils.py
    """

    def __init__(
        self,
        should_write_to_storage_fn: Callable[[object], bool],
        rehydrate_fn: Callable[[object, object], Any] = lambda self, x: x,
        default_value=None,
    ):
        self.default_value = default_value
        self.rehydrate_fn = rehydrate_fn
        self.should_write_to_storage_fn = should_write_to_storage_fn

    def __set_name__(self, owner, name):
        # Validate that the owner class has the methods we need
        assert issubclass(
            owner, ArchiveFieldInterface
        ), "Missing some required methods to use AchiveField"
        self.public_name = name
        self.db_field_name = "_" + name
        self.archive_field_name = "_" + name + "_storage_path"
        self.table_name = owner._meta.db_table

    @lru_cache(maxsize=1)
    def _get_value_from_archive(self, obj):
        repository = obj.get_repository()
        archive_service = ArchiveService(repository=repository)
        archive_field = getattr(obj, self.archive_field_name)
        try:
            file_str = archive_service.read_file(archive_field)
            return self.rehydrate_fn(obj, json.loads(file_str))
        except FileNotInStorageError:
            log.error(
                "Archive enabled field not in storage",
                extra=dict(
                    storage_path=archive_field,
                    object_id=obj.id,
                    commit=obj.get_commitid(),
                ),
            )
            return self.default_value

    def __get__(self, obj, objtype=None):
        db_field = getattr(obj, self.db_field_name)
        if db_field is not None:
            return self.rehydrate_fn(obj, db_field)
        return self._get_value_from_archive(obj)

    def __set__(self, obj, value):
        self._get_value_from_archive.cache_clear()
        # Set the new value
        if self.should_write_to_storage_fn(obj):
            repository = obj.get_repository()
            archive_service = ArchiveService(repository=repository)
            path = archive_service.write_json_data_to_storage(
                commit_id=obj.get_commitid(),
                table=self.table_name,
                field=self.public_name,
                external_id=obj.external_id,
                data=value,
            )
            setattr(obj, self.archive_field_name, path)
            setattr(obj, self.db_field_name, None)
        else:
            setattr(obj, self.db_field_name, value)
