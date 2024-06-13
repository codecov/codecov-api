import uuid
from typing import Optional

from codecov.commands.base import BaseCommand
from codecov_auth.models import Owner
from core.models import Repository
from timeseries.models import MeasurementName

from .interactors.activate_measurements import ActivateMeasurementsInteractor
from .interactors.encode_secret_string import EncodeSecretStringInteractor
from .interactors.erase_repository import EraseRepositoryInteractor
from .interactors.fetch_repository import FetchRepositoryInteractor
from .interactors.get_repository_token import GetRepositoryTokenInteractor
from .interactors.get_upload_token import GetUploadTokenInteractor
from .interactors.regenerate_repository_token import RegenerateRepositoryTokenInteractor
from .interactors.regenerate_repository_upload_token import (
    RegenerateRepositoryUploadTokenInteractor,
)
from .interactors.update_repository import UpdateRepositoryInteractor


class RepositoryCommands(BaseCommand):
    def fetch_repository(self, owner, name):
        return self.get_interactor(FetchRepositoryInteractor).execute(owner, name)

    def regenerate_repository_upload_token(
        self,
        repo_name: str,
        owner_username: str,
    ) -> uuid.UUID:
        return self.get_interactor(RegenerateRepositoryUploadTokenInteractor).execute(
            repo_name, owner_username
        )

    def update_repository(
        self,
        repo_name: str,
        owner: Owner,
        default_branch: Optional[str],
        activated: Optional[bool],
    ):
        return self.get_interactor(UpdateRepositoryInteractor).execute(
            repo_name, owner, default_branch, activated
        )

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

    def encode_secret_string(self, owner: Owner, repo_name: str, value: str):
        return self.get_interactor(EncodeSecretStringInteractor).execute(
            owner, repo_name, value
        )
