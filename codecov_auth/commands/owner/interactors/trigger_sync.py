from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated
from services.refresh import RefreshService


class TriggerSyncInteractor(BaseInteractor):
    def validate(self):
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    def execute(self):
        self.validate()
        RefreshService().trigger_refresh(
            self.current_user.ownerid,
            self.current_user.username,
            using_integration=False,
        )
