from codecov.commands.base import BaseCommand

from .interactors.get_upload_error import GetUploadErrorInteractor
from .interactors.get_upload_presigned_url import GetUploadPresignedUrlInteractor


class UploadCommands(BaseCommand):
    def get_upload_errors(self, upload):
        return self.get_interactor(GetUploadErrorInteractor).execute(upload)

    def get_upload_presigned_url(self, upload):
        return self.get_interactor(GetUploadPresignedUrlInteractor).execute(upload)
