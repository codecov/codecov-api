from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated
from codecov_auth.helpers import current_user_part_of_org
from codecov_auth.models import RepositoryToken


class GetProfilingTokenInteractor(BaseInteractor):
    def validate(self):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    @sync_to_async
    def execute(self, repository):
        self.validate()
        if current_user_part_of_org(self.current_user, repository.author):
            token = RepositoryToken.objects.filter(
                repository_id=repository.repoid, token_type="profiling"
            ).first()
            if token:
                return token.key
