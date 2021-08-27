from codecov.commands.base import BaseCommand
from services.repo_providers import RepoProviderService
from .interactors.fetch_commit import FetchCommitInteractor
from .interactors.get_final_yaml import GetFinalYamlInteractor
from .interactors.get_uploads_of_commit import GetUploadsOfCommitInteractor
from .interactors.get_file_content import GetFileContentInteractor
from .interactors.get_commit_report import GetCommitReportInteractor
from services.archive import ReportService


class CommitCommands(BaseCommand):
    def get_commit_report(self, commit):
        return self.get_interactor(GetCommitReportInteractor).execute(commit)

    def get_file_content(self, commit, path):
        return self.get_interactor(GetFileContentInteractor).execute(commit, path)

    def fetch_commit(self, repository, commit_id):
        return self.get_interactor(FetchCommitInteractor).execute(repository, commit_id)

    def get_final_yaml(self, commit):
        return self.get_interactor(GetFinalYamlInteractor).execute(commit)

    def get_uploads_of_commit(self, commit):
        return self.get_interactor(GetUploadsOfCommitInteractor).execute(commit)
