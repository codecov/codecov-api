import json
from unittest.mock import MagicMock, patch

from django.forms import ValidationError
from django.test import TestCase
from shared.storage.exceptions import FileNotInStorageError

from core.models import Commit
from reports.tests.factories import CommitReportFactory

from .factories import CommitFactory, RepositoryFactory


class RepoTests(TestCase):
    def test_clean_repo(self):
        repo = RepositoryFactory(using_integration=None)
        with self.assertRaises(ValidationError):
            repo.clean()


class CommitTests(TestCase):
    def test_commitreport_no_code(self):
        commit = CommitFactory()
        report1 = CommitReportFactory(
            commit=commit, code="testing"
        )  # this is a report for a "local upload"
        report2 = CommitReportFactory(commit=commit, code=None)
        assert commit.commitreport == report2

    sample_report = {
        "files": {
            "different/test_file.py": [
                2,
                [0, 10, 8, 2, 0, "80.00000", 0, 0, 0, 0, 0, 0, 0],
                [[0, 10, 8, 2, 0, "80.00000", 0, 0, 0, 0, 0, 0, 0]],
                [0, 2, 1, 1, 0, "50.00000", 0, 0, 0, 0, 0, 0, 0],
            ],
        },
        "sessions": {
            "0": {
                "N": None,
                "a": "v4/raw/2019-01-10/4434BC2A2EC4FCA57F77B473D83F928C/abf6d4df662c47e32460020ab14abf9303581429/9ccc55a1-8b41-4bb1-a946-ee7a33a7fb56.txt",
                "c": None,
                "d": 1547084427,
                "e": None,
                "f": ["unittests"],
                "j": None,
                "n": None,
                "p": None,
                "t": [3, 20, 17, 3, 0, "85.00000", 0, 0, 0, 0, 0, 0, 0],
                "": None,
            }
        },
    }

    @patch("utils.model_utils.ArchiveService")
    def test_get_report_from_db(self, mock_archive):
        commit = CommitFactory()
        mock_read_file = MagicMock()
        mock_archive.return_value.read_file = mock_read_file
        commit._report = self.sample_report
        commit._files_array_storage_path = None
        commit.save()

        fetched = Commit.objects.get(id=commit.id)
        assert fetched.report == self.sample_report
        mock_archive.assert_not_called()
        mock_read_file.assert_not_called()

    @patch("utils.model_utils.ArchiveService")
    def test_get_report_from_storage(self, mock_archive):
        commit = CommitFactory()
        storage_path = "https://storage/path/report.json"
        mock_read_file = MagicMock(return_value=json.dumps(self.sample_report))
        mock_archive.return_value.read_file = mock_read_file
        commit._report = None
        commit._report_storage_path = storage_path
        commit.save()

        fetched = Commit.objects.get(id=commit.id)
        assert fetched.report == self.sample_report
        mock_archive.assert_called()
        mock_read_file.assert_called_with(storage_path)
        # Calls it again to test caching
        assert fetched.report == self.sample_report
        assert mock_archive.call_count == 1
        assert mock_read_file.call_count == 1
        # This one to help us understand caching across different instances
        # different instances if they are the same
        assert commit.report == self.sample_report
        assert mock_archive.call_count == 1
        assert mock_read_file.call_count == 1
        # Let's see for objects with different IDs
        diff_commit = CommitFactory()
        storage_path = "https://storage/path/files_array.json"
        diff_commit._report = None
        diff_commit._report_storage_path = storage_path
        diff_commit.save()
        assert diff_commit.report == self.sample_report
        assert mock_archive.call_count == 2
        assert mock_read_file.call_count == 2

    @patch("utils.model_utils.ArchiveService")
    def test_get_report_from_storage_file_not_found(self, mock_archive):
        commit = CommitFactory()
        storage_path = "https://storage/path/files_array.json"

        def side_effect(*args, **kwargs):
            raise FileNotInStorageError()

        mock_read_file = MagicMock(side_effect=side_effect)
        mock_archive.return_value.read_file = mock_read_file
        commit._report = None
        commit._report_storage_path = storage_path
        commit.save()

        fetched = Commit.objects.get(id=commit.id)
        assert fetched._report_storage_path == storage_path
        assert fetched.report == {}
        mock_archive.assert_called()
        mock_read_file.assert_called_with(storage_path)
