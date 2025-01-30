from codecov.commands.base import BaseInteractor
from codecov.db import sync_to_async
from codecov_auth.models import RepositoryToken


class RegenerateRepositoryTokenInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, repo_name: str, owner_username: str, token_type: str):
        _owner, repo = self.resolve_owner_and_repo(
            owner_username, repo_name, only_viewable=True, only_active=True
        )

        token, created = RepositoryToken.objects.get_or_create(
            repository_id=repo.repoid, token_type=token_type
        )
        if not created:
            token.key = token.generate_key()
            token.save()
        return token.key
