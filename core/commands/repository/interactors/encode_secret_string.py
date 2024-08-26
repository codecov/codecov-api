from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov.db import sync_to_async
from codecov_auth.models import Owner
from core.commands.repository.interactors.utils import encode_secret_string
from core.models import Repository


class EncodeSecretStringInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, owner: Owner, repo_name: str, value: str) -> str:
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

        repo = Repository.objects.viewable_repos(owner).filter(name=repo_name).first()
        if not repo:
            raise ValidationError("Repo not found")
        to_encode = "/".join(
            (
                owner.service,
                owner.service_id,
                repo.service_id,
                value,
            )
        )
        return encode_secret_string(to_encode)
