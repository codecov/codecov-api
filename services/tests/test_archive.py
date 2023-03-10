from pathlib import Path
from time import time
from unittest.mock import patch

from core.tests.factories import RepositoryFactory
from services.archive import ArchiveService
from services.storage import StorageService

current_file = Path(__file__)


class ArchiveServiceTests:
    def test_create_raw_upload_presigned_put(self, db, mocker, codecov_vcr):
        mocked = mocker.patch.object(StorageService, "create_presigned_put")
        mocked.return_value = "presigned url"
        repo = RepositoryFactory.create()
        service = ArchiveService(repo)
        assert service.create_raw_upload_presigned_put("ABCD") == "presigned url"

    def test_create_raw_upload_presigned_get(self, db, mocker):
        mocked = mocker.patch.object(StorageService, "create_presigned_get")
        mocked.return_value = "presigned url"
        repo = RepositoryFactory.create()
        service = ArchiveService(repo)
        assert (
            service.create_raw_upload_presigned_get(
                filename="random.txt", commit_sha="abc"
            )
            == "presigned url"
        )

    @patch("services.storage.MINIO_CLIENT.presigned_get_object")
    def test_create_presigned_get_minio_client(self, mock_storage_get, db):
        storage = StorageService()
        mock_storage_get.return_value = "minio_presigned_get_url"

        url = "v4/repos/aaaa/commits/{}/file.txt".format(int(time()))

        assert (
            storage.create_presigned_get("hasna", url, 10) == "minio_presigned_get_url"
        )
