from typing import Union

from shared.reports.resources import Report

from codecov.commands.base import BaseCommand
from services.comparison import Comparison, ComparisonReport, PullRequestComparison

from .interactors.fetch_impacted_files import FetchImpactedFiles


class CompareCommands(BaseCommand):
    def fetch_impacted_files(
        self,
        comparison_report: ComparisonReport,
        comparison: Union[PullRequestComparison, Comparison],
        filters,
    ):
        return self.get_interactor(FetchImpactedFiles).execute(
            comparison_report, comparison, filters
        )
