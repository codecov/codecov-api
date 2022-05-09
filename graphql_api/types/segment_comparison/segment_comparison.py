from typing import List

from ariadne import ObjectType

from services.comparison import LineComparison, SegmentComparison

segment_comparison_bindable = ObjectType("SegmentComparison")


@segment_comparison_bindable.field("header")
def resolve_header(segment_comparison: SegmentComparison, info) -> str:
    (
        base_starting,
        base_extracted,
        head_starting,
        head_extracted,
    ) = segment_comparison.header
    base = f"{base_starting}"
    if base_extracted is not None:
        base = f"{base},{base_extracted}"
    head = f"{head_starting}"
    if head_extracted is not None:
        head = f"{head},{head_extracted}"
    return f"@@ -{base} +{head} @@"


@segment_comparison_bindable.field("lines")
def resolve_lines(segment_comparison: SegmentComparison, info) -> List[LineComparison]:
    return segment_comparison.lines
