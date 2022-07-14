import json

import minio
from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor
from codecov_auth.commands.owner import OwnerCommands
from core.commands.repository import RepositoryCommands
from core.models import Repository
from graphql_api.types.enums import UploadState
from reports.models import UploadError
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

    def get_repo_from_upload(self, repoid):
        repo = Repository.objects.get(repoid=repoid)
        if repo is None:
            raise Exception("Repo could not be found")
        return repo

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
            )

        except minio.error.NoSuchKey as e:
            raise Exception("Requested report could not be found")

    @sync_to_async
    def execute(self, upload):
        repo = self.get_repo_from_upload(repoid=upload.report.commit.repository_id)
        return self.get_upload_presigned_url(
            repo=repo, download_url=upload.download_url
        )
