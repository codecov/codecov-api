import json
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase
from shared.storage import MinioStorageService

from core.tests.factories import RepositoryFactory
from services.archive import ArchiveService

current_file = Path(__file__)


class ArchiveServiceTests(TestCase):
    @patch("services.storage.StorageService.create_presigned_put")
    def test_create_raw_upload_presigned_put(self, create_presigned_put_mock):
        create_presigned_put_mock.return_value = "presigned url"
        repo = RepositoryFactory.create()
        service = ArchiveService(repo)
        assert service.create_raw_upload_presigned_put("ABCD") == "presigned url"


class TestWriteData(object):
    def test_write_report_details_to_storage(self, mocker, db):
        repo = RepositoryFactory()
        mock_write_file = mocker.patch.object(MinioStorageService, "write_file")

        data = [
            {
                "filename": "file_1.go",
                "file_index": 0,
                "file_totals": [0, 8, 5, 3, 0, "62.50000", 0, 0, 0, 0, 10, 2, 0],
                "session_totals": {
                    "0": [0, 8, 5, 3, 0, "62.50000", 0, 0, 0, 0, 10, 2],
                    "meta": {"session_count": 1},
                },
                "diff_totals": None,
            },
            {
                "filename": "file_2.py",
                "file_index": 1,
                "file_totals": [0, 2, 1, 0, 1, "50.00000", 1, 0, 0, 0, 0, 0, 0],
                "session_totals": {
                    "0": [0, 2, 1, 0, 1, "50.00000", 1],
                    "meta": {"session_count": 1},
                },
                "diff_totals": None,
            },
        ]
        archive_service = ArchiveService(repository=repo)
        commitid = "some-commit-sha"
        external_id = "some-uuid4-id"
        path = archive_service.write_json_data_to_storage(
            commit_id=commitid,
            table="reports_reportsdetails",
            field="files_array",
            external_id=external_id,
            data=data,
        )
        assert (
            path
            == f"v4/repos/{archive_service.storage_hash}/commits/{commitid}/json_data/reports_reportsdetails/files_array/{external_id}.json"
        )
        mock_write_file.assert_called_with(
            archive_service.root,
            path,
            json.dumps(data),
            gzipped=False,
            reduced_redundancy=False,
        )

    def test_write_report_details_to_storage_no_commitid(self, mocker, db):
        repo = RepositoryFactory()
        mock_write_file = mocker.patch.object(MinioStorageService, "write_file")

        data = [
            {
                "filename": "file_1.go",
                "file_index": 0,
                "file_totals": [0, 8, 5, 3, 0, "62.50000", 0, 0, 0, 0, 10, 2, 0],
                "session_totals": {
                    "0": [0, 8, 5, 3, 0, "62.50000", 0, 0, 0, 0, 10, 2],
                    "meta": {"session_count": 1},
                },
                "diff_totals": None,
            },
            {
                "filename": "file_2.py",
                "file_index": 1,
                "file_totals": [0, 2, 1, 0, 1, "50.00000", 1, 0, 0, 0, 0, 0, 0],
                "session_totals": {
                    "0": [0, 2, 1, 0, 1, "50.00000", 1],
                    "meta": {"session_count": 1},
                },
                "diff_totals": None,
            },
        ]
        archive_service = ArchiveService(repository=repo)
        commitid = None
        external_id = "some-uuid4-id"
        path = archive_service.write_json_data_to_storage(
            commit_id=commitid,
            table="reports_reportsdetails",
            field="files_array",
            external_id=external_id,
            data=data,
        )
        assert (
            path
            == f"v4/repos/{archive_service.storage_hash}/json_data/reports_reportsdetails/files_array/{external_id}.json"
        )
        mock_write_file.assert_called_with(
            archive_service.root,
            path,
            json.dumps(data),
            gzipped=False,
            reduced_redundancy=False,
        )
