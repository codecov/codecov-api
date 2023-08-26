import json
import logging
from typing import Any, Callable, Optional

from shared.storage.exceptions import FileNotInStorageError
from shared.utils.ReportEncoder import ReportEncoder

from services.archive import ArchiveService

log = logging.getLogger(__name__)


class ArchiveFieldInterfaceMeta(type):
    def __subclasscheck__(cls, subclass):
        return (
            hasattr(subclass, "get_repository")
            and callable(subclass.get_repository)
            and hasattr(subclass, "get_commitid")
            and callable(subclass.get_commitid)
            and hasattr(subclass, "external_id")
        )


class ArchiveFieldInterface(metaclass=ArchiveFieldInterfaceMeta):
    """Any class that uses ArchiveField must implement this interface"""

    external_id: str

    def get_repository(self):
        """Returns the repository object associated with self"""
        raise NotImplementedError()

    def get_commitid(self) -> Optional[str]:
        """Returns the commitid associated with self.
        If no commitid is associated return None.
        """
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
        json_encoder=ReportEncoder,
        default_value_class=lambda: None,
    ):
        self.default_value_class = default_value_class
        self.rehydrate_fn = rehydrate_fn
        self.should_write_to_storage_fn = should_write_to_storage_fn
        self.json_encoder = json_encoder

    def __set_name__(self, owner, name):
        # Validate that the owner class has the methods we need
        assert issubclass(
            owner, ArchiveFieldInterface
        ), "Missing some required methods to use AchiveField"
        self.public_name = name
        self.db_field_name = "_" + name
        self.archive_field_name = "_" + name + "_storage_path"
        self.cached_value_property_name = f"__{self.public_name}_cached_value"

    def _get_value_from_archive(self, obj):
        repository = obj.get_repository()
        archive_service = ArchiveService(repository=repository)
        archive_field = getattr(obj, self.archive_field_name)
        if archive_field:
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
        else:
            log.debug(
                "Both db_field and archive_field are None",
                extra=dict(
                    object_id=obj.id,
                    commit=obj.get_commitid(),
                ),
            )
        return self.default_value_class()

    def __get__(self, obj, objtype=None):
        cached_value = getattr(obj, self.cached_value_property_name, None)
        if cached_value:
            return cached_value
        db_field = getattr(obj, self.db_field_name)
        if db_field is not None:
            value = self.rehydrate_fn(obj, db_field)
        else:
            value = self._get_value_from_archive(obj)
        setattr(obj, self.cached_value_property_name, value)
        return value

    def __set__(self, obj, value):
        # Set the new value
        if self.should_write_to_storage_fn(obj):
            repository = obj.get_repository()
            archive_service = ArchiveService(repository=repository)
            old_file_path = getattr(obj, self.archive_field_name)
            table_name = obj._meta.db_table
            path = archive_service.write_json_data_to_storage(
                commit_id=obj.get_commitid(),
                table=table_name,
                field=self.public_name,
                external_id=obj.external_id,
                data=value,
                encoder=self.json_encoder,
            )
            if old_file_path is not None and path != old_file_path:
                archive_service.delete_file(old_file_path)
            setattr(obj, self.archive_field_name, path)
            setattr(obj, self.db_field_name, None)
        else:
            setattr(obj, self.db_field_name, value)
        setattr(obj, self.cached_value_property_name, value)
