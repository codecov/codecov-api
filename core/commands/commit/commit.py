from codecov.commands.base import BaseCommand

from .interactors.fetch_commits import FetchCommitsInteractor
from .interactors.fetch_totals import FetchTotalsInteractor
from .interactors.get_commit_errors import GetCommitErrorsInteractor
from .interactors.get_file_content import GetFileContentInteractor
from .interactors.get_final_yaml import GetFinalYamlInteractor
from .interactors.get_uploads_number import GetUploadsNumberInteractor


class CommitCommands(BaseCommand):
    def get_file_content(self, commit, path):
        return self.get_interactor(GetFileContentInteractor).execute(commit, path)

    def fetch_commits(self, repository, filters):
        return self.get_interactor(FetchCommitsInteractor).execute(repository, filters)

    def fetch_totals(self, commit):
        return self.get_interactor(FetchTotalsInteractor).execute(commit)

    def get_final_yaml(self, commit):
        return self.get_interactor(GetFinalYamlInteractor).execute(commit)

    def get_commit_errors(self, commit, error_type):
        return self.get_interactor(GetCommitErrorsInteractor).execute(
            commit, error_type
        )

    def get_uploads_number(self, commit):
        return self.get_interactor(GetUploadsNumberInteractor).execute(commit)
