from functools import cached_property
from typing import List, Optional

from ariadne import ObjectType
from asgiref.sync import sync_to_async

from services.comparison import FileComparison, SegmentComparison

file_comparison_bindable = ObjectType("FileComparison")


@file_comparison_bindable.field("baseName")
def resolve_base_name(file_comparison: FileComparison, info) -> Optional[str]:
    return file_comparison.name["base"]


@file_comparison_bindable.field("headName")
def resolve_head_name(file_comparison: FileComparison, info) -> Optional[str]:
    return file_comparison.name["head"]


@file_comparison_bindable.field("isNewFile")
def resolve_is_new_file(file_comparison: FileComparison, info) -> bool:
    base_name = file_comparison.name["base"]
    head_name = file_comparison.name["head"]
    return base_name is None and head_name is not None


@file_comparison_bindable.field("hasDiff")
def resolve_has_diff(file_comparison: FileComparison, info) -> bool:
    return file_comparison.has_diff


@file_comparison_bindable.field("hasChanges")
def resolve_has_changes(file_comparison: FileComparison, info) -> bool:
    return file_comparison.has_changes


@file_comparison_bindable.field("baseTotals")
def resolve_base_totals(file_comparison: FileComparison, info) -> dict:
    return file_comparison.totals["base"]


@file_comparison_bindable.field("headTotals")
def resolve_head_totals(file_comparison: FileComparison, info) -> dict:
    return file_comparison.totals["head"]


@file_comparison_bindable.field("segments")
@sync_to_async
def resolve_segments(file_comparison: FileComparison, info) -> List[SegmentComparison]:
    if file_comparison.has_changes:
        comparison = info.context["comparison"]

        # this file comparison has coverage changes - reinstantiate with the
        # full source code so we can include relevant segments
        file_comparison = comparison.get_file_comparison(
            file_comparison.name["head"], with_src=True, bypass_max_diff=True
        )
    return file_comparison.segments
