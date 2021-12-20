from codecov.commands.base import BaseCommand

from .interactors.get_upload_error import GetUploadErrorInteractor


class UploadCommands(BaseCommand):
    def get_upload_errors(self, upload):
        return self.get_interactor(GetUploadErrorInteractor).execute(upload)
