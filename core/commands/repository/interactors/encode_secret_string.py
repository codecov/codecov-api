from dataclasses import dataclass

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov.db import sync_to_async
from codecov_auth.models import Owner, RepositoryToken
from core.models import Repository
from utils import encode_secret_string


@dataclass
class EncodeSecretStringInput:
    value: str = ""
    repoName: str = ""


class EncodeSecretStringInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, owner: Owner, input: EncodeSecretStringInput):
        string_to_encode = input.get("value")
        repo_name = input.get("repoNmae")

        author = Owner.objects.filter(username=owner.name, service=self.service).first()

        repo = (
            Repository.objects.viewable_repos(self.current_owner)
            .filter(author=author, name=repo_name, active=True)
            .first()
        )

        to_encode = "/".join(
            (
                owner.service,
                owner.service_id,
                repo.service_id,
                string_to_encode,
            )
        )

        return encode_secret_string(to_encode)
