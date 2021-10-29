from unittest.mock import patch

import minio
from ddf import G
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from codecov_auth.models import Owner
from core.models import Repository


class UploadDownloadHelperTest(APITestCase):
    def _get(self, kwargs={}, data={}):
        path = f"/upload/{kwargs.get('service')}/{kwargs.get('owner_username')}/{kwargs.get('repo_name')}/download"
        return self.client.get(path, data=data)

    def setUp(self):
        self.org = G(Owner, username="codecovtest", service="github")
        self.repo = G(
            Repository,
            author=self.org,
            name="upload-test-repo",
            upload_token="test27s4f3uz3ha9pi0foipg5bqojtrmbt67",
        )
        self.repo = G(
            Repository, author=self.org, name="private-upload-test-repo", private=True
        )

    def test_no_path_param(self):
        response = self._get()
        assert response.status_code == 404

    def test_invalid_path_param(self):
        response = self._get(data={"path": "v2"})
        assert response.status_code == 404

    def test_invalid_owner(self):
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": "invalid",
                "repo_name": "invalid",
            },
            data={"path": "v4/raw"},
        )
        assert response.status_code == 404

    def test_invalid_repo(self):
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": "codecovtest",
                "repo_name": "invalid",
            },
            data={"path": "v4/raw"},
        )
        assert response.status_code == 404

    @patch("services.archive.ArchiveService.get_archive_hash")
    @patch("services.archive.ArchiveService.read_file")
    def test_invalid_archive_path(self, read_file, get_archive_hash):
        read_file.side_effect = [minio.error.NoSuchKey]
        get_archive_hash.return_value = "path"
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": "codecovtest",
                "repo_name": "upload-test-repo",
            },
            data={"path": "v4/raw/path"},
        )
        assert response.status_code == 404

    @patch("services.archive.ArchiveService.get_archive_hash")
    @patch("services.archive.ArchiveService.read_file")
    def test_valid_repo_archive_path(self, mock_read_file, get_archive_hash):
        mock_read_file.return_value = "Report!"
        get_archive_hash.return_value = "hasssshhh"
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": "codecovtest",
                "repo_name": "upload-test-repo",
            },
            data={"path": "v4/raw/hasssshhh"},
        )
        assert response.status_code == 200
        headers = response._headers
        assert headers["content-type"] == ("Content-Type", "text/plain")

    @patch("services.archive.ArchiveService.read_file")
    def test_invalid_repo_archive_path(self, mock_read_file):
        mock_read_file.return_value = "Report!"
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": "codecovtest",
                "repo_name": "upload-test-repo",
            },
            data={"path": "v4/raw"},
        )
        assert response.status_code == 404

    def test_private_valid_archive_path(self):
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": "codecovtest",
                "repo_name": "private-upload-test-repo",
            },
            data={"path": "v4/raw"},
        )
        assert response.status_code == 404
