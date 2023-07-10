import json
import logging
from functools import lru_cache
from typing import Any, Callable, Tuple

from shared.storage.exceptions import FileNotInStorageError

from services.archive import ArchiveService

log = logging.getLogger(__name__)


class GCSDecorator(object):
    """This is a helper class that transparently handles models' fields that are saved in GCS."""

    def __init__(
        self,
        decorated_class_name: str,
        db_field_name: str,
        gcs_field_name: str,
        attributes_to_repository: Tuple[str],
        attributes_to_commit: Tuple[str],
    ):
        self.db_field_name = db_field_name
        self.gcs_field_name = gcs_field_name
        self.attributes_to_repository = attributes_to_repository
        self.attributes_to_commit = attributes_to_commit
        self.class_name = decorated_class_name

    def _follow_attributes_list(self, object: Any, attributes_list: Tuple[str]):
        try:
            for attribute_name in attributes_list:
                object = getattr(object, attribute_name)
        except AttributeError:
            log.exception("Failed to follow attribute list")
            return None
        return object

    def get_repo(self, obj_ref, fail_on_error=False):
        repo = self._follow_attributes_list(obj_ref, self.attributes_to_repository)
        if repo is None and fail_on_error:
            raise Exception("Failed to get repository for GCS decorated field")
        return repo

    def get_commitid(self, obj_ref, fail_on_error=False):
        commitid = self._follow_attributes_list(
            obj_ref, self.attributes_to_commit + ("commitid",)
        )
        if commitid is None and fail_on_error:
            raise Exception("Failed to get commitid for GCS decorated field")
        return commitid

    def get_gcs_enabled_field(
        self,
        *,
        default_value_fn: Callable[[], Any],
    ) -> Callable:
        """This method can be used as the fget argument with property().
        It uses @lru_cache to avoid hitting GCS multiple times.

        Note: If you are also using set_gcs_enabled_field method they need to come from the same
        GCSDecorator instance. Otherwise the cache cleaning won't work.
        """

        @lru_cache(maxsize=1)
        def _decorator(obj_ref):
            try:
                db_field_value = getattr(obj_ref, self.db_field_name)
                gcs_field_value = getattr(obj_ref, self.gcs_field_name)
            except AttributeError:
                log.exception("Failed to get GCS enabled field. Config error.")
                return default_value_fn()
            if db_field_value:
                return db_field_value
            repository = self.get_repo(obj_ref)
            archive_service = ArchiveService(repository=repository)
            try:
                file_str = archive_service.read_file(gcs_field_value)
                return json.loads(file_str)
            except FileNotInStorageError:
                log.error(
                    "GCS enabled field not in storage",
                    extra=dict(
                        storage_path=self.gcs_field_name,
                        object_id=obj_ref.id,
                        commit=self.get_commitid(obj_ref),
                    ),
                )
                return default_value_fn()

        # We need this ref to clear the cache when setting
        self.getter_fn_ref = _decorator
        return self.getter_fn_ref

    def set_gcs_enabled_field(
        self,
        *,
        should_write_to_storage_fn: Callable[[Any], bool],
    ):
        def _decorator(obj_ref, val: Any):
            # Invalidate the cache for the getter method
            self.getter_fn_ref.cache_clear()
            # Thrown AttributeError if the values are not configured properly
            db_field_value = getattr(obj_ref, self.db_field_name)
            gcs_field_value = getattr(obj_ref, self.gcs_field_name)
            # Set the new value
            if should_write_to_storage_fn(obj_ref):
                repository = self.get_repo(obj_ref, fail_on_error=True)
                archive_service = ArchiveService(repository=repository)
                path = archive_service.write_json_data_to_storage(
                    commit_id=self.get_commitid(obj_ref, fail_on_error=True),
                    model=self.class_name,
                    field=self.gcs_field_name,
                    external_id=obj_ref.external_id,
                    data=val,
                )
                setattr(obj_ref, self.gcs_field_name, path)
                setattr(obj_ref, self.db_field_name, None)
            else:
                setattr(obj_ref, self.db_field_name, val)

        return _decorator
