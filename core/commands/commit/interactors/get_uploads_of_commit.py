from asgiref.sync import sync_to_async

from codecov.commands.base import BaseInteractor
from reports.models import ReportSession


class GetUploadsOfCommitInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, commit):
        if not commit.commitreport:
            # TODO: return error here missing head commit
            return ReportSession.objects.none()
        return (
            commit.commitreport.sessions.prefetch_related("flags")
            .order_by("upload_type")
            .all()
            .reverse()
        )
