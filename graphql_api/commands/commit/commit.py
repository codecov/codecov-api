from ..base import BaseCommand

from .interactors.fetch_commit import FetchCommitInteractor


class CommitCommands(BaseCommand):
    def fetch_commit(self, repository, commit_id):
        return self.get_interactor(FetchCommitInteractor).execute(repository, commit_id)
