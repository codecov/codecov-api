from codecov.commands.base import BaseCommand
from codecov_auth.models import Owner

from .interactors.activate_measurements import ActivateMeasurementsInteractor
from .interactors.erase_repository import EraseRepositoryInteractor
from core.models import Repository
from timeseries.models import MeasurementName

from .interactors.activate_measurements import ActivateMeasurementsInteractor
from .interactors.encode_secret_string import EncodeSecretStringInteractor
from .interactors.fetch_repository import FetchRepositoryInteractor
from .interactors.get_repository_token import GetRepositoryTokenInteractor
from .interactors.get_upload_token import GetUploadTokenInteractor
from .interactors.regenerate_repository_token import RegenerateRepositoryTokenInteractor


class RepositoryCommands(BaseCommand):
    def fetch_repository(self, owner, name):
        return self.get_interactor(FetchRepositoryInteractor).execute(owner, name)

    def get_upload_token(self, repository):
        return self.get_interactor(GetUploadTokenInteractor).execute(repository)

    def get_repository_token(self, repository, token_type):
        return self.get_interactor(GetRepositoryTokenInteractor).execute(
            repository, token_type
        )

    def regenerate_repository_token(
        self, repo_name: str, owner_username: str, token_type: str
    ):
        return self.get_interactor(RegenerateRepositoryTokenInteractor).execute(
            repo_name, owner_username, token_type
        )

    def activate_measurements(
        self, repo_name: str, owner_name: str, measurement_type: MeasurementName
    ):
        return self.get_interactor(ActivateMeasurementsInteractor).execute(
            repo_name, owner_name, measurement_type
        )

    def erase_repository(self, repo_name: str, owner: Owner):
        return self.get_interactor(EraseRepositoryInteractor).execute(repo_name, owner)
      
    def encode_secret_string(self, owner: Owner, repo: Repository, value: str):
        return self.get_interactor(EncodeSecretStringInteractor).execute(
            owner, repo, value
        )
