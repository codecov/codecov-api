import json
from unittest.mock import MagicMock

from shared.storage.exceptions import FileNotInStorageError
from shared.utils.ReportEncoder import ReportEncoder

from core.models import Commit
from core.tests.factories import CommitFactory
from utils.model_utils import ArchiveField, ArchiveFieldInterface


class TestArchiveField(object):
    class ClassWithArchiveField(object):

        commit: Commit
        id = 1
        external_id = "external_id"
        _meta = MagicMock(db_table="test_table")

        _archive_field = "db_field"
        _archive_field_storage_path = "archive_field_path"

        def should_write_to_storage(self):
            return self.should_write_to_gcs

        def get_repository(self):
            return self.commit.repository

        def get_commitid(self):
            return self.commit.commitid

        def __init__(
            self, commit, db_value, archive_value, should_write_to_gcs=False
        ) -> None:
            self.commit = commit
            self._archive_field = db_value
            self._archive_field_storage_path = archive_value
            self.should_write_to_gcs = should_write_to_gcs

        archive_field = ArchiveField(
            should_write_to_storage_fn=should_write_to_storage, default_value=None
        )

    class ClassWithArchiveFieldMissingMethods:
        commit: Commit
        id = 1
        external_id = "external_id"

    def test_subclass_validation(self, mocker):
        assert issubclass(
            self.ClassWithArchiveField(
                mocker.MagicMock(), mocker.MagicMock(), mocker.MagicMock()
            ),
            ArchiveFieldInterface,
        )
        assert not issubclass(
            self.ClassWithArchiveFieldMissingMethods, ArchiveFieldInterface
        )

    def test_archive_getter_db_field_set(self, db):
        commit = CommitFactory()
        test_class = self.ClassWithArchiveField(commit, "db_value", "gcs_path")
        assert test_class._archive_field == "db_value"
        assert test_class._archive_field_storage_path == "gcs_path"
        assert test_class.archive_field == "db_value"

    def test_archive_getter_archive_field_set(self, db, mocker):
        some_json = {"some": "data"}
        mock_read_file = mocker.MagicMock(return_value=json.dumps(some_json))
        mock_archive_service = mocker.patch("utils.model_utils.ArchiveService")
        mock_archive_service.return_value.read_file = mock_read_file
        commit = CommitFactory()
        test_class = self.ClassWithArchiveField(commit, None, "gcs_path")

        assert test_class._archive_field == None
        assert test_class._archive_field_storage_path == "gcs_path"
        assert test_class.archive_field == some_json
        mock_read_file.assert_called_with("gcs_path")
        mock_archive_service.assert_called_with(repository=commit.repository)
        assert mock_read_file.call_count == 1
        # Test that caching also works
        assert test_class.archive_field == some_json
        assert mock_read_file.call_count == 1

    def test_archive_getter_file_not_in_storage(self, db, mocker):
        mock_read_file = mocker.MagicMock(side_effect=FileNotInStorageError())
        mock_archive_service = mocker.patch("utils.model_utils.ArchiveService")
        mock_archive_service.return_value.read_file = mock_read_file
        commit = CommitFactory()
        test_class = self.ClassWithArchiveField(commit, None, "gcs_path")

        assert test_class._archive_field == None
        assert test_class._archive_field_storage_path == "gcs_path"
        assert test_class.archive_field == None
        mock_read_file.assert_called_with("gcs_path")
        mock_archive_service.assert_called_with(repository=commit.repository)

    def test_archive_setter_db_field(self, db, mocker):
        commit = CommitFactory()
        test_class = self.ClassWithArchiveField(commit, "db_value", "gcs_path", False)
        assert test_class._archive_field == "db_value"
        assert test_class._archive_field_storage_path == "gcs_path"
        assert test_class.archive_field == "db_value"
        mock_archive_service = mocker.patch("utils.model_utils.ArchiveService")
        test_class.archive_field = "batata frita"
        mock_archive_service.assert_not_called()
        assert test_class._archive_field == "batata frita"
        assert test_class.archive_field == "batata frita"

    def test_archive_setter_archive_field(self, db, mocker):
        commit = CommitFactory()
        test_class = self.ClassWithArchiveField(commit, "db_value", None, True)
        some_json = {"some": "data"}
        mock_read_file = mocker.MagicMock(return_value=json.dumps(some_json))
        mock_write_file = mocker.MagicMock(return_value="path/to/written/object")
        mock_archive_service = mocker.patch("utils.model_utils.ArchiveService")
        mock_archive_service.return_value.read_file = mock_read_file
        mock_archive_service.return_value.write_json_data_to_storage = mock_write_file

        assert test_class._archive_field == "db_value"
        assert test_class._archive_field_storage_path == None
        assert test_class.archive_field == "db_value"
        assert mock_read_file.call_count == 0

        # Pretend there was something in the path.
        # This should happen, but it will help us test the deletion of old data saved
        test_class._archive_field_storage_path = "path/to/old/data"

        # Now we write to the property
        test_class.archive_field = some_json
        assert test_class._archive_field == None
        assert test_class._archive_field_storage_path == "path/to/written/object"
        assert test_class.archive_field == some_json
        # Writing cleans the cache
        assert mock_read_file.call_count == 1
        mock_read_file.assert_called_with("path/to/written/object")
        mock_write_file.assert_called_with(
            commit_id=commit.commitid,
            table="test_table",
            field="archive_field",
            external_id=test_class.external_id,
            data=some_json,
            encoder=ReportEncoder,
        )
        mock_archive_service.return_value.delete_file.assert_called_with(
            "path/to/old/data"
        )
