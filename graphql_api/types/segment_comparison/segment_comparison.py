from dataclasses import dataclass
from typing import List, Optional

from ariadne import ObjectType, UnionType

from graphql_api.types.errors.errors import ProviderError, QueryError, UnknownPath
from services.comparison import LineComparison, Segment


@dataclass
class SegmentComparisons:
    results: List[Segment]


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
def resolve_has_unintended_changes(segment: Segment, info) -> bool:
    return segment.has_unintended_changes


segments_result_bindable = UnionType("SegmentsResult")


@segments_result_bindable.type_resolver
def resolve_segments_result_type(res, *_):
    if isinstance(res, UnknownPath):
        return "UnknownPath"
    elif isinstance(res, ProviderError):
        return "ProviderError"
    elif isinstance(res, SegmentComparisons):
        return "SegmentComparisons"
    elif isinstance(res, QueryError):
        return "QueryError"
