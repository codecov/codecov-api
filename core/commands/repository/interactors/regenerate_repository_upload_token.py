import uuid

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import ValidationError
from codecov.db import sync_to_async
from codecov_auth.models import Owner
from core.models import Repository


class RegenerateRepositoryUploadTokenInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, repo_name: str, owner_username: str) -> uuid.UUID:
        author = Owner.objects.filter(
            username=owner_username, service=self.service
        ).first()
        repo = (
            Repository.objects.viewable_repos(self.current_owner)
            .filter(author=author, name=repo_name)
            .first()
        )
        if not repo:
            raise ValidationError("Repo not found")
        repo.upload_token = uuid.uuid4()
        repo.save()
        return repo.upload_token
