from typing import List

from django.utils.functional import cached_property
from shared.components import Component
from shared.reports.filtered import FilteredReport
from shared.reports.resources import Report
from shared.reports.types import ReportTotals

from codecov_auth.models import Owner
from core.models import Commit
from services.comparison import Comparison
from services.yaml import final_commit_yaml


def commit_components(commit: Commit, user: Owner) -> List[Component]:
    """
    Get the list of components for a commit.
    A request is made to the provider on behalf of the given `user`
    to fetch the commit YAML (from which component config is parsed).
    """
    yaml = final_commit_yaml(commit, user)
    return yaml.get_components()


def component_filtered_report(report: Report, component: Component) -> FilteredReport:
    """
    Filter a report such that the totals, etc. are only pertaining to the given component.
    """
    flags = component.get_matching_flags(report.flags.keys())
    filtered_report = report.filter(flags=flags, paths=component.paths)
    return filtered_report


class ComponentComparison:
    def __init__(self, comparison: Comparison, component: Component):
        self.comparison = comparison
        self.component = component

    @cached_property
    def base_report(self) -> FilteredReport:
        return component_filtered_report(self.comparison.base_report, self.component)

    @cached_property
    def head_report(self) -> FilteredReport:
        return component_filtered_report(self.comparison.head_report, self.component)

    @cached_property
    def patch_totals(self) -> ReportTotals:
        git_comparison = self.comparison.git_comparison
        return self.head_report.apply_diff(git_comparison["diff"])
