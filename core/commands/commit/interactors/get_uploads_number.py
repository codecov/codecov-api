from codecov.commands.base import BaseInteractor
from codecov.db import sync_to_async


class GetUploadsNumberInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, commit):
        if not commit.commitreport:
            return 0
        return len(commit.commitreport.sessions.all())
