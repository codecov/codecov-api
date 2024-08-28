from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import ValidationError
from codecov.db import sync_to_async
from codecov_auth.models import Owner, RepositoryToken
from core.models import Repository


class RegenerateRepositoryTokenInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, repo_name: str, owner_username: str, token_type: str):
        author = Owner.objects.filter(
            username=owner_username, service=self.service
        ).first()
        repo = (
            Repository.objects.viewable_repos(self.current_owner)
            .filter(author=author, name=repo_name, active=True)
            .first()
        )
        if not repo:
            raise ValidationError("Repo not found")

        token, created = RepositoryToken.objects.get_or_create(
            repository_id=repo.repoid, token_type=token_type
        )
        if not created:
            token.key = token.generate_key()
            token.save()
        return token.key
