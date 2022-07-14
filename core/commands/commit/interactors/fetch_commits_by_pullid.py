from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor
from core.models import Commit


class FetchCommitsByPullidInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, pull):
        return Commit.objects.filter(
            pullid=pull.pullid,
            repository_id=pull.repository_id,
        ).exclude(deleted=True)
