from services.archive import ReportService
from codecov.commands.base import BaseInteractor
from asgiref.sync import sync_to_async


class GetFileCoverageInteractor(BaseInteractor):
    @sync_to_async
    def get_file_coverage(self, commit, path):
        report_service = ReportService()
        report = report_service.build_report_from_commit(commit)

        file_report = report.get(path)
        return [
            {"line": line_report[0], "coverage": line_report[1].coverage}
            for line_report in file_report.lines
        ]

    def execute(self, commit, path):
        return self.get_file_coverage(commit, path)
