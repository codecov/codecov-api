from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated
from codecov.db import sync_to_async
from codecov_auth.helpers import current_user_part_of_org
from codecov_auth.models import RepositoryToken


class GetRepositoryTokenInteractor(BaseInteractor):
    def validate(self, repository):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    @sync_to_async
    def execute(self, repository, token_type):
        self.validate(repository)
        if not repository.active:
            return None

        if current_user_part_of_org(self.current_owner, repository.author):
            token = RepositoryToken.objects.filter(
                repository_id=repository.repoid, token_type=token_type
            ).first()
            if not token:
                token = RepositoryToken(
                    repository_id=repository.repoid, token_type=token_type
                )
                token.save()
            return token.key
