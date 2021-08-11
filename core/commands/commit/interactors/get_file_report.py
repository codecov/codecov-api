from services.archive import ReportService
from codecov.commands.base import BaseInteractor
from asgiref.sync import sync_to_async


class GetFileReportInteractor(BaseInteractor):
    @sync_to_async
    def get_line_coverage(self, commit, path):
        report_service = ReportService()
        report = report_service.build_report_from_commit(commit)
        return report.get(path)

    def execute(self, commit, path):
        return self.get_line_coverage(commit, path)
