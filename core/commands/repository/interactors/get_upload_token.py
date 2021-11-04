from codecov.commands.base import BaseInteractor
from codecov_auth.helpers import current_user_part_of_org
from core.models import Repository


class GetUploadTokenInteractor(BaseInteractor):
    async def execute(self, repository):
        if not current_user_part_of_org(self.current_user, repository.author):
            return None
        return repository.upload_token
