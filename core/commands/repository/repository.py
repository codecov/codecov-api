from codecov.commands.base import BaseCommand

from .interactors.fetch_repository import FetchRepositoryInteractor
from .interactors.get_upload_token import GetUploadTokenInteractor


class RepositoryCommands(BaseCommand):
    def fetch_repository(self, owner, name):
        return self.get_interactor(FetchRepositoryInteractor).execute(owner, name)

    def get_upload_token(self, repository):
        return self.get_interactor(GetUploadTokenInteractor).execute(repository)
