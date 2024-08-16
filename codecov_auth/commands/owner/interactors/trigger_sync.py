from codecov.commands.base import BaseInteractor
from codecov.commands.exceptions import Unauthenticated
from codecov.db import sync_to_async
from services.refresh import RefreshService


class TriggerSyncInteractor(BaseInteractor):
    def validate(self) -> None:
        if not self.current_user.is_authenticated:
            raise Unauthenticated()

    @sync_to_async
    def execute(self) -> None:
        self.validate()
        RefreshService().trigger_refresh(
            self.current_owner.ownerid,
            self.current_owner.username,
            using_integration=False,
            manual_trigger=True,
        )
