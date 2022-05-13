from typing import Optional

from ariadne import ObjectType
from shared.utils.merge import LineType

from graphql_api.types.enums import CoverageLine
from services.comparison import LineComparison

line_coverages = {
    LineType.hit: CoverageLine.H,
    LineType.miss: CoverageLine.M,
    LineType.partial: CoverageLine.P,
}


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
    return line_comparison.value
