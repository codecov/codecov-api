from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated
from codecov.db import sync_to_async
from codecov_auth.models import UserToken


class RevokeUserTokenInteractor(BaseInteractor):
    def validate(self):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    @sync_to_async
    def execute(self, tokenid):
        self.validate()
        UserToken.objects.filter(external_id=tokenid, owner=self.current_user).delete()
