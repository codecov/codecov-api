import json

from shared.storage.exceptions import FileNotInStorageError

from core.models import Commit
from core.tests.factories import CommitFactory
from utils.model_utils import GCSDecorator

gcs_decorator = GCSDecorator(
    decorated_class_name="TestClass",
    db_field_name="db_field",
    gcs_field_name="gcs_field",
    attributes_to_repository=("commit", "repository"),
    attributes_to_commit=("commit",),
)


class TestGCSDecorator(object):
    class TestClass(object):
        commit: Commit
        db_field: str
        gcs_field: str
        id = 1
        external_id = "external_id"

        wrapped_property = property(
            fget=gcs_decorator.get_gcs_enabled_field(default_value_fn=lambda: None),
            fset=gcs_decorator.set_gcs_enabled_field(
                should_write_to_storage_fn=lambda self: self.should_write_to_gcs
            ),
        )

        wrapped_property_bad_config = property(
            fget=GCSDecorator(
                decorated_class_name="TestClass",
                db_field_name="db_field",
                gcs_field_name="field_doesnt_exist",
                attributes_to_repository=("commit", "repository"),
                attributes_to_commit=("commit",),
            ).get_gcs_enabled_field(default_value_fn=lambda: "default_value")
        )

        def __init__(
            self, commit, db_field_value, gcs_field_value, should_write_to_gcs=False
        ) -> None:
            self.commit = commit
            self.db_field = db_field_value
            self.gcs_field = gcs_field_value
            self.should_write_to_gcs = should_write_to_gcs

    def test_gcs_getter_db_field_set(self, db):
        commit = CommitFactory()
        test_class = self.TestClass(commit, "db_value", "gcs_path")
        assert test_class.db_field == "db_value"
        assert test_class.gcs_field == "gcs_path"
        assert test_class.wrapped_property == "db_value"

    def test_gcs_getter_gcs_field_set(self, db, mocker):
        some_json = {"some": "data"}
        mock_read_file = mocker.MagicMock(return_value=json.dumps(some_json))
        mock_archive_service = mocker.patch("utils.model_utils.ArchiveService")
        mock_archive_service.return_value.read_file = mock_read_file
        commit = CommitFactory()
        test_class = self.TestClass(commit, None, "gcs_path")

        assert test_class.db_field == None
        assert test_class.gcs_field == "gcs_path"
        assert test_class.wrapped_property == some_json
        mock_read_file.assert_called_with("gcs_path")
        mock_archive_service.assert_called_with(repository=commit.repository)
        assert mock_read_file.call_count == 1
        # Test that caching also works
        assert test_class.wrapped_property == some_json
        assert mock_read_file.call_count == 1

    def test_gcs_getter_field_doesnt_exist(self, db):
        commit = CommitFactory()
        test_class = self.TestClass(commit, "db_value", "gcs_path")
        assert test_class.db_field == "db_value"
        assert test_class.gcs_field == "gcs_path"
        assert test_class.wrapped_property_bad_config == "default_value"

    def test_gcs_getter_file_not_in_storage(self, db, mocker):
        mock_read_file = mocker.MagicMock(side_effect=FileNotInStorageError())
        mock_archive_service = mocker.patch("utils.model_utils.ArchiveService")
        mock_archive_service.return_value.read_file = mock_read_file
        commit = CommitFactory()
        test_class = self.TestClass(commit, None, "gcs_path")

        assert test_class.db_field == None
        assert test_class.gcs_field == "gcs_path"
        assert test_class.wrapped_property == None
        mock_read_file.assert_called_with("gcs_path")
        mock_archive_service.assert_called_with(repository=commit.repository)

    def test_gcs_setter_db_field(self, db, mocker):
        commit = CommitFactory()
        test_class = self.TestClass(commit, "db_value", "gcs_path", False)
        assert test_class.db_field == "db_value"
        assert test_class.gcs_field == "gcs_path"
        assert test_class.wrapped_property == "db_value"
        mock_archive_service = mocker.patch("utils.model_utils.ArchiveService")
        test_class.wrapped_property = "batata frita"
        mock_archive_service.assert_not_called()
        assert test_class.db_field == "batata frita"
        assert test_class.wrapped_property == "batata frita"

    def test_gcs_setter_gcs_field(self, db, mocker):
        commit = CommitFactory()
        test_class = self.TestClass(commit, "db_value", None, True)
        some_json = {"some": "data"}
        mock_read_file = mocker.MagicMock(return_value=json.dumps(some_json))
        mock_write_file = mocker.MagicMock(return_value="path/to/written/object")
        mock_archive_service = mocker.patch("utils.model_utils.ArchiveService")
        mock_archive_service.return_value.read_file = mock_read_file
        mock_archive_service.return_value.write_json_data_to_storage = mock_write_file

        assert test_class.db_field == "db_value"
        assert test_class.gcs_field == None
        assert test_class.wrapped_property == "db_value"
        assert mock_read_file.call_count == 0

        # Now we write to the property
        test_class.wrapped_property = some_json
        assert test_class.db_field == None
        assert test_class.gcs_field == "path/to/written/object"
        assert test_class.wrapped_property == some_json
        # Writing cleans the cache
        assert mock_read_file.call_count == 1
        mock_read_file.assert_called_with("path/to/written/object")
        mock_write_file.assert_called()
