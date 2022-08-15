from codecov.commands.base import BaseCommand

from .interactors.fetch_commits import FetchCommitsInteractor
from .interactors.fetch_commits_by_pullid import FetchCommitsByPullidInteractor
from .interactors.fetch_totals import FetchTotalsInteractor
from .interactors.get_commit_errors import GetCommitErrorsInteractor
from .interactors.get_file_content import GetFileContentInteractor
from .interactors.get_final_yaml import GetFinalYamlInteractor
from .interactors.get_uploads_of_commit import GetUploadsOfCommitInteractor


class CommitCommands(BaseCommand):
    def get_file_content(self, commit, path):
        return self.get_interactor(GetFileContentInteractor).execute(commit, path)

    def fetch_commits(self, repository, filters):
        return self.get_interactor(FetchCommitsInteractor).execute(repository, filters)

    def fetch_commits_by_pullid(self, pull):
        return self.get_interactor(FetchCommitsByPullidInteractor).execute(pull)

    def fetch_totals(self, commit):
        return self.get_interactor(FetchTotalsInteractor).execute(commit)

    def get_final_yaml(self, commit):
        return self.get_interactor(GetFinalYamlInteractor).execute(commit)

    def get_uploads_of_commit(self, commit):
        return self.get_interactor(GetUploadsOfCommitInteractor).execute(commit)

    def get_commit_errors(self, commit, errorType):
        return self.get_interactor(GetCommitErrorsInteractor).execute(commit, errorType)
