from typing import List, Optional
from xmlrpc.client import Boolean

from ariadne import ObjectType

from services.comparison import LineComparison, Segment

segment_comparison_bindable = ObjectType("SegmentComparison")


@segment_comparison_bindable.field("header")
def resolve_header(segment: Segment, info) -> Optional[str]:
    (
        base_starting,
        base_extracted,
        head_starting,
        head_extracted,
    ) = segment.header
    base = f"{base_starting}"
    if base_extracted is not None:
        base = f"{base},{base_extracted}"
    head = f"{head_starting}"
    if head_extracted is not None:
        head = f"{head},{head_extracted}"
    return f"-{base} +{head}"


@segment_comparison_bindable.field("lines")
def resolve_lines(segment: Segment, info) -> List[LineComparison]:
    return segment.lines


@segment_comparison_bindable.field("hasUnintendedChanges")
def resolve_has_unintended_changes(segment: Segment, info) -> Boolean:
    return segment.has_unintended_changes
