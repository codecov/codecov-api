import minio
from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor
from codecov_auth.commands.owner import OwnerCommands
from core.commands.repository import RepositoryCommands
from graphql_api.types.enums import UploadState
from reports.models import UploadError
from services.archive import ArchiveService


class GetUploadPresignedUrlInteractor(BaseInteractor):
    def read_download_url(self):
        download_url = self.download_url.rsplit("/")
        self.file_name = download_url[-1]
        self.commitid = download_url[-2]
        self.date_string = download_url[-4]
        self.repo_name = download_url[4]
        self.owner_username = download_url[3]

    async def read_repo(self):
        owner = await OwnerCommands(self.current_user, self.service).fetch_owner(
            self.owner_username
        )
        repo = await RepositoryCommands(
            self.current_user, self.service
        ).fetch_repository(owner, self.repo_name)
        if repo is None:
            raise Exception("Unable to find repo")
        self.repo = repo

    async def get_upload_presigned_url(self):
        archive_service = ArchiveService(self.repo)

        # Verify that the repo hash in the path matches the repo in the URL by generating the repo hash
        if archive_service.storage_hash not in self.download_url:
            raise Exception("Requested report could not be found")
        try:
            return archive_service.create_raw_upload_presigned_get(
                commit_sha=self.commitid,
                filename=self.file_name,
                date_string=self.date_string,
            )

        except minio.error.NoSuchKey as e:
            raise Exception("Requested report could not be found")

    async def execute(self, upload):
        self.download_url = upload.download_url
        self.read_download_url()
        await self.read_repo()

        return await self.get_upload_presigned_url()
