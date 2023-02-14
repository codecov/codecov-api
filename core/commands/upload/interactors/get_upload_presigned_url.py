import minio

from codecov.commands.base import BaseInteractor
from codecov.db import sync_to_async
from core.models import Repository
from services.archive import ArchiveService


class GetUploadPresignedUrlInteractor(BaseInteractor):
    def get_url_parts(self, download_url):
        url = download_url.rsplit("/")
        file_name = url[-1]
        commitid = url[-2]
        date_string = url[-4]

        return {
            "file_name": file_name,
            "commitid": commitid,
            "date_string": date_string,
        }

    def get_upload_presigned_url(self, repo, download_url):
        archive_service = ArchiveService(repo)
        download_url_parts = self.get_url_parts(download_url=download_url)

        if archive_service.storage_hash not in download_url:
            raise Exception("Requested report could not be found")
        try:
            return archive_service.create_raw_upload_presigned_get(
                commit_sha=download_url_parts["commitid"],
                filename=download_url_parts["file_name"],
                date_string=download_url_parts["date_string"],
                expires=300,
            )

        except minio.error.NoSuchKey as e:
            raise Exception("Requested report could not be found")

    @sync_to_async
    def execute(self, upload):
        repo = upload.report.commit.repository

        return self.get_upload_presigned_url(
            repo=repo, download_url=upload.download_url
        )
