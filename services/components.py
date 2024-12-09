from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from django.utils.functional import cached_property
from shared.components import Component
from shared.reports.filtered import FilteredReport
from shared.reports.resources import Report
from shared.reports.types import ReportTotals

from codecov_auth.models import Owner
from core.models import Commit
from services.comparison import Comparison
from services.yaml import final_commit_yaml
from timeseries.helpers import fill_sparse_measurements
from timeseries.models import Interval


def commit_components(commit: Commit, owner: Owner | None) -> List[Component]:
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


def filter_components_by_name_or_id(
    components: List[Component], terms: List[str]
) -> List[Component]:
    """
    Given a list of Components and a list of strings (terms),
    return a new list of Components only including Components with names in terms (case insensitive)
    OR component_id in terms (case insensitive)
    """
    terms = [v.lower() for v in terms]
    return [
        component
        for component in components
        if component.name.lower() in terms or component.component_id.lower() in terms
    ]


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


class ComponentMeasurements:
    def __init__(
        self,
        raw_measurements: List[dict],
        component_id: str,
        interval: Interval,
        after: datetime,
        before: datetime,
        last_measurement: datetime,
        components_mapping: Dict[str, str],
    ):
        self.raw_measurements = raw_measurements
        self.component_id = component_id
        self.interval = interval
        self.after = after
        self.before = before
        self.last_measurement = last_measurement
        self.components_mapping = components_mapping

    @cached_property
    def name(self) -> str:
        if self.components_mapping.get(self.component_id):
            return self.components_mapping[self.component_id]
        return self.component_id

    @cached_property
    def component_id(self) -> str:
        return self.component_id

    @cached_property
    def percent_covered(self) -> Optional[float]:
        if len(self.raw_measurements) > 0:
            return self.raw_measurements[-1]["avg"]

    @cached_property
    def percent_change(self) -> Optional[float]:
        if len(self.raw_measurements) > 1:
            return self.raw_measurements[-1]["avg"] - self.raw_measurements[0]["avg"]

    @cached_property
    def measurements(self) -> Iterable[Dict[str, Any]]:
        if not self.raw_measurements:
            return []
        return fill_sparse_measurements(
            self.raw_measurements, self.interval, self.after, self.before
        )

    @cached_property
    def last_uploaded(self) -> datetime:
        return self.last_measurement
