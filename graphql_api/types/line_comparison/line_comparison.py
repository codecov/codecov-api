from functools import cached_property
from typing import List, Optional

from ariadne import ObjectType
from shared.utils.merge import LineType

from graphql_api.types.enums import CoverageLine
from services.comparison import LineComparison

line_coverages = {
    LineType.hit: CoverageLine.H,
    LineType.miss: CoverageLine.M,
    LineType.partial: CoverageLine.P,
}


class CoverageInfo:
    def __init__(
        self,
        line_comparison: LineComparison,
        ignored_upload_ids: Optional[List[int]] = None,
    ):
        self.line_comparison = line_comparison
        self.ignored_upload_ids = set(ignored_upload_ids or [])

    @cached_property
    def hit_count(self):
        upload_ids = self.hit_upload_ids
        if upload_ids is not None:
            return len(upload_ids)

    @cached_property
    def hit_upload_ids(self):
        upload_ids = self.line_comparison.hit_session_ids
        if upload_ids is not None:
            return set(upload_ids) - self.ignored_upload_ids


line_comparison_bindable = ObjectType("LineComparison")


@line_comparison_bindable.field("baseNumber")
def resolve_base_number(line_comparison: LineComparison, info) -> Optional[str]:
    return line_comparison.number["base"]


@line_comparison_bindable.field("headNumber")
def resolve_head_number(line_comparison: LineComparison, info) -> Optional[str]:
    return line_comparison.number["head"]


@line_comparison_bindable.field("baseCoverage")
def resolve_base_coverage(line_comparison: LineComparison, info) -> Optional[str]:
    line_type: LineType = line_comparison.coverage["base"]
    if line_type is not None:
        return line_coverages.get(line_type)


@line_comparison_bindable.field("headCoverage")
def resolve_head_coverage(line_comparison: LineComparison, info) -> Optional[str]:
    line_type: LineType = line_comparison.coverage["head"]
    if line_type is not None:
        return line_coverages.get(line_type)


@line_comparison_bindable.field("content")
def resolve_content(line_comparison: LineComparison, info) -> str:
    value = line_comparison.value
    if value and line_comparison.is_diff:
        return f"{value[0]} {value[1:]}"
    return f" {value}"


@line_comparison_bindable.field("coverageInfo")
def resolve_coverage_info(
    line_comparison: LineComparison,
    info,
    ignored_upload_ids: Optional[List[int]] = None,
) -> CoverageInfo:
    return CoverageInfo(line_comparison, ignored_upload_ids=ignored_upload_ids)
