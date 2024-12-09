from unittest.mock import patch

import minio
from ddf import G
from rest_framework.test import APITransactionTestCase

from codecov_auth.models import Owner
from core.models import Repository


class UploadDownloadHelperTest(APITransactionTestCase):
    def _get(self, kwargs={}, data={}):
        path = f"/upload/{kwargs.get('service')}/{kwargs.get('owner_username')}/{kwargs.get('repo_name')}/download"
        return self.client.get(path, data=data)

    def setUp(self):
        self.org = G(Owner, username="codecovtest", service="github")
        self.repo = G(
            Repository,
            author=self.org,
            name="upload-test-repo",
            upload_token="a03e5d02-9495-4413-b0d8-05651bb2e842",
        )
        self.repo = G(
            Repository, author=self.org, name="private-upload-test-repo", private=True
        )

    def test_no_path_param(self):
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": "codecovtest",
                "repo_name": "invalid",
            },
        )
        assert response.status_code == 404

    def test_invalid_path_param(self):
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": "codecovtest",
                "repo_name": "invalid",
            },
            data={"path": "v2"},
        )
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

    @patch("shared.api_archive.archive.ArchiveService.get_archive_hash")
    @patch("shared.api_archive.archive.StorageService.create_presigned_get")
    def test_invalid_archive_path(self, create_presigned_get, get_archive_hash):
        create_presigned_get.side_effect = [
            minio.error.S3Error(
                code="NoSuchKey",
                message=None,
                resource=None,
                request_id=None,
                host_id=None,
                response=None,
            )
        ]
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

    @patch("shared.api_archive.archive.ArchiveService.get_archive_hash")
    @patch("shared.api_archive.archive.StorageService.create_presigned_get")
    def test_valid_repo_archive_path(self, create_presigned_get, get_archive_hash):
        create_presigned_get.return_value = "presigned-url"
        get_archive_hash.return_value = "hasssshhh"
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": "codecovtest",
                "repo_name": "upload-test-repo",
            },
            data={"path": "v4/raw/hasssshhh"},
        )
        assert response.status_code == 302
        headers = response.headers
        assert headers["location"] == "presigned-url"
        create_presigned_get.assert_called_once_with(
            "archive", "v4/raw/hasssshhh", expires=30
        )

    @patch("shared.api_archive.archive.ArchiveService.read_file")
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

    def test_invalid_shelter_path(self):
        response = self._get(
            kwargs={
                "service": "gh",
                "owner_username": "codecovtest",
                "repo_name": "upload-test-repo",
            },
            data={"path": "shelter/github/codecovtest::::some-other-repo"},
        )
        assert response.status_code == 404
