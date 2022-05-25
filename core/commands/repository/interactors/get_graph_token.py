from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated
from codecov_auth.helpers import current_user_part_of_org


class GetGraphTokenInteractor(BaseInteractor):
    def validate(self):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    async def execute(self, repository):
        self.validate()

        if not current_user_part_of_org(self.current_user, repository.author):
            return None
        return repository.image_token
