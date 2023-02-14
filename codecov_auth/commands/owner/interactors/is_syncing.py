from codecov.commands.base import BaseInteractor
from codecov.db import sync_to_async
from services.refresh import RefreshService


class IsSyncingInteractor(BaseInteractor):
    @sync_to_async
    def execute(self):
        return RefreshService().is_refreshing(self.current_user.ownerid)
