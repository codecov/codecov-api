from asgiref.sync import sync_to_async

from services.archive import ReportService
from codecov.commands.base import BaseInteractor


class GetCommitReportInteractor(BaseInteractor):
    @sync_to_async
    def execute(self, commit):
        report_service = ReportService()
        return report_service.build_report_from_commit(commit)
