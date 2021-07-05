from codecov.commands.base import BaseCommand

from .interactors.fetch_commit import FetchCommitInteractor
from .interactors.get_final_yaml import GetFinalYamlInteractor
from .interactors.get_uploads_of_commit import GetUploadsOfCommitInteractor


class CommitCommands(BaseCommand):
    def fetch_commit(self, repository, commit_id):
        return self.get_interactor(FetchCommitInteractor).execute(repository, commit_id)

    def get_final_yaml(self, commit):
        return self.get_interactor(GetFinalYamlInteractor).execute(commit)

    def get_uploads_of_commit(self, commit):
        return self.get_interactor(GetUploadsOfCommitInteractor).execute(commit)
