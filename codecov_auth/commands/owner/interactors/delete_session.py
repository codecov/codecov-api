from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated, Unauthorized
from codecov.db import sync_to_async
from codecov_auth.models import Session


class DeleteSessionInteractor(BaseInteractor):
    def validate(self):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    @sync_to_async
    def execute(self, sessionid):
        self.validate()
        Session.objects.filter(sessionid=sessionid, owner=self.current_owner).delete()
