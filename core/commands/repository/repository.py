from codecov.commands.base import BaseCommand

from .interactors.activate_flags_measurements import ActivateFlagsMeasurementsInteractor
from .interactors.fetch_repository import FetchRepositoryInteractor
from .interactors.get_profiling_token import GetProfilingTokenInteractor
from .interactors.get_upload_token import GetUploadTokenInteractor
from .interactors.regenerate_repository_token import RegenerateRepositoryTokenInteractor


class RepositoryCommands(BaseCommand):
    def fetch_repository(self, owner, name):
        return self.get_interactor(FetchRepositoryInteractor).execute(owner, name)

    def get_upload_token(self, repository):
        return self.get_interactor(GetUploadTokenInteractor).execute(repository)

    def get_profiling_token(self, repository):
        return self.get_interactor(GetProfilingTokenInteractor).execute(repository)

    def regenerate_repository_token(
        self, repo_name: str, owner_username: str, token_type: str
    ):
        return self.get_interactor(RegenerateRepositoryTokenInteractor).execute(
            repo_name, owner_username, token_type
        )

    def activate_flags_measurements(self, repo_name, owner_name):
        return self.get_interactor(ActivateFlagsMeasurementsInteractor).execute(
            repo_name, owner_name
        )
