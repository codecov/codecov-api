from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor
from core.models import Commit


class FetchPullCommitsInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, pull):
        commits = Commit.objects.filter(pullid=pull.pullid)
        return commits
