from unittest.mock import patch

import minio
import pytest
from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory
from reports.tests.factories import CommitReportFactory, UploadFactory

from ..get_upload_presigned_url import GetUploadPresignedUrlInteractor


class GetUploadPresignedUrlInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory()
        self.randomOwner = OwnerFactory()
        repo = RepositoryFactory(author=self.org, private=True)
        commit = CommitFactory(repository=repo)
        commit_report = CommitReportFactory(commit=commit)
        self.upload = UploadFactory(
            report=commit_report,
            storage_path="v4/raw/2022-06-23/942173DE95CBF167C5683F40B7DB34C0/ee3ecad424e67419d6c4531540f1ef5df045ff12/919ccc6d-7972-4895-b289-f2d569683a17.txt",
        )

    def execute(self, user, *args):
        service = user.service if user else "github"
        return GetUploadPresignedUrlInteractor(user, service).execute(*args)

    async def test_get_presigned_url_repo_not_found(self):
        with pytest.raises(Exception):
            await self.execute(self.randomOwner, self.upload)

    @patch("services.archive.ArchiveService.get_archive_hash")
    @patch("services.archive.ArchiveService.create_raw_upload_presigned_get")
    async def test_noSuchKey_minio_error(
        self, create_raw_upload_presigned_get, get_archive_hash
    ):
        create_raw_upload_presigned_get.side_effect = [minio.error.NoSuchKey]
        get_archive_hash.return_value = "path"

        with pytest.raises(Exception):
            await self.execute(self.org, self.upload)

    @patch("services.archive.ArchiveService.get_archive_hash")
    @patch("services.archive.ArchiveService.create_raw_upload_presigned_get")
    async def test_invalid_archive_storage_path(
        self, create_raw_upload_presigned_get, get_archive_hash
    ):
        create_raw_upload_presigned_get = "mocked presigned url"
        get_archive_hash.return_value = "random"

        with pytest.raises(Exception):
            await self.execute(self.org, self.upload)

    @patch("services.archive.ArchiveService.create_raw_upload_presigned_get")
    @patch("services.archive.ArchiveService.get_archive_hash")
    async def test_get_presigned_url(
        self, get_archive_hash, create_raw_upload_presigned_get
    ):
        get_archive_hash.return_value = "942173DE95CBF167C5683F40B7DB34C0"
        create_raw_upload_presigned_get.return_value = "presigned_url_mock"

        presigned_url = await self.execute(self.org, self.upload)
        assert presigned_url == "presigned_url_mock"
