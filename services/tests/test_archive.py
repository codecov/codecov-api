from pathlib import Path
from time import time
from unittest.mock import patch

from django.test import TestCase

from core.tests.factories import RepositoryFactory
from services.archive import ArchiveService
from services.storage import StorageService

current_file = Path(__file__)


class ArchiveServiceTests(TestCase):
    @patch("services.storage.StorageService.create_presigned_put")
    def test_create_raw_upload_presigned_put(self, create_presigned_put_mock):
        create_presigned_put_mock.return_value = "presigned url"
        repo = RepositoryFactory.create()
        service = ArchiveService(repo)
        assert service.create_raw_upload_presigned_put("ABCD") == "presigned url"
