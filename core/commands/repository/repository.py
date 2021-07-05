from codecov.commands.base import BaseCommand

from .interactors.fetch_repository import FetchRepositoryInteractor


class RepositoryCommands(BaseCommand):
    def fetch_repository(self, owner, name):
        return self.get_interactor(FetchRepositoryInteractor).execute(owner, name)
