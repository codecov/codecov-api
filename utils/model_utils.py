import json
import logging
from functools import lru_cache

from shared.storage.exceptions import FileNotInStorageError

from core.models import Repository
from services.archive import ArchiveService

log = logging.getLogger(__name__)


class ArchiveFieldInterfaceMeta(type):
    def __instancecheck__(cls, instance):
        return cls.__subclasscheck__(type(instance))

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
    def get_repository(self) -> Repository:
        raise NotImplementedError()

    def get_commitid(self) -> str:
        raise NotImplementedError()

    def should_write_to_storage(self) -> bool:
        raise NotImplementedError()


class ArchiveField:
    """This is a helper class that transparently handles models' fields that are saved in GCS.
    It uses the Descriptor pattern: https://docs.python.org/3/howto/descriptor.html
    """

    def __init__(self, default_value=None):
        self.default_value = default_value

    def __set_name__(self, owner, name):
        # Validate that the owner class has the methods we need
        assert issubclass(
            owner, ArchiveFieldInterface
        ), "Missing some required methods to use AchiveField"
        self.public_name = name
        self.db_field_name = "_" + name
        self.archive_field_name = "_" + name + "_storage_path"
        self.class_name = owner.__name__

    @lru_cache(maxsize=1)
    def _get_value_from_archive(self, obj):
        repository = obj.get_repository()
        archive_service = ArchiveService(repository=repository)
        archive_field = getattr(obj, self.archive_field_name)
        try:
            file_str = archive_service.read_file(archive_field)
            return json.loads(file_str)
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
            return db_field
        return self._get_value_from_archive(obj)

    def __set__(self, obj, value):
        self._get_value_from_archive.cache_clear()
        # Set the new value
        if obj.should_write_to_storage():
            repository = obj.get_repository()
            archive_service = ArchiveService(repository=repository)
            path = archive_service.write_json_data_to_storage(
                commit_id=obj.get_commitid(),
                model=self.class_name,
                field=self.public_name,
                external_id=obj.external_id,
                data=value,
            )
            setattr(obj, self.archive_field_name, path)
            setattr(obj, self.db_field_name, None)
        else:
            setattr(obj, self.db_field_name, value)
