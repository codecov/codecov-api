from asgiref.sync import sync_to_async
from graphql_api.commands.base import BaseInteractor

from reports.models import ReportSession


class GetUploadsOfCommitInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, commit):
        report = commit.reports.first()
        if not report:
            return ReportSession.objects.none()
        return report.sessions.prefetch_related("flags").all()
