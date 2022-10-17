from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor


class GetUploadsNumberInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, commit):
        if not commit.commitreport:
            return 0
        return len(commit.commitreport.sessions.prefetch_related("flags").all())
