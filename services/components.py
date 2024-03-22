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


def commit_components(commit: Commit, owner: Owner) -> List[Component]:
    """
    Get the list of components for a commit.
    A request is made to the provider on behalf of the given `owner`
    to fetch the commit YAML (from which component config is parsed).
    """
    yaml = final_commit_yaml(commit, owner)
    return yaml.get_components()


def component_filtered_report(
    report: Report, components: List[Component]
) -> FilteredReport:
    """
    Filter a report such that the totals, etc. are only pertaining to the given component.
    """
    flags, paths = [], []
    for component in components:
        flags.extend(component.get_matching_flags(report.flags.keys()))
        paths.extend(component.paths)
    filtered_report = report.filter(flags=flags, paths=paths)
    return filtered_report


def filter_components_by_name(
    components: List[Component], terms: List[str]
) -> List[Component]:
    """
    Given a list of Components and a list of strings (terms),
    return a new list of Components only including Components with names in terms (case insensitive)
    """
    terms = [v.lower() for v in terms]
    return list(filter(lambda c: c.name.lower() in terms, components))


class ComponentComparison:
    def __init__(self, comparison: Comparison, component: Component):
        self.comparison = comparison
        self.component = component

    @cached_property
    def base_report(self) -> FilteredReport:
        return component_filtered_report(self.comparison.base_report, [self.component])

    @cached_property
    def head_report(self) -> FilteredReport:
        return component_filtered_report(self.comparison.head_report, [self.component])

    @cached_property
    def base_totals(self) -> ReportTotals:
        return self.base_report.totals

    @cached_property
    def head_totals(self) -> ReportTotals:
        return self.head_report.totals

    @cached_property
    def patch_totals(self) -> ReportTotals:
        git_comparison = self.comparison.git_comparison
        return self.head_report.apply_diff(git_comparison["diff"])
