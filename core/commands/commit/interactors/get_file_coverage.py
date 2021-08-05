from services.archive import ReportService
from codecov.commands.base import BaseInteractor
from asgiref.sync import sync_to_async
from fractions import Fraction
import math


class GetFileCoverageInteractor(BaseInteractor):
    def get_coverage(self, _coverage):
        if _coverage == 1:
            return 1
        elif _coverage == 0:
            return 0
        elif type(_coverage) is str:
            partial = math.ceil(float(Fraction(_coverage)))
            return 0 if partial == 0 else 2

    @sync_to_async
    def get_file_coverage(self, commit, path):
        report_service = ReportService()
        report = report_service.build_report_from_commit(commit)

        file_report = report.get(path)
        return [
            {
                "line": line_report[0],
                "coverage": self.get_coverage(line_report[1].coverage),
            }
            for line_report in file_report.lines
        ]

    def execute(self, commit, path):
        return self.get_file_coverage(commit, path)
