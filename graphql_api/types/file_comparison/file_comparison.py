from functools import cached_property
from typing import List, Optional

from ariadne import ObjectType

from codecov.db import sync_to_async
from services.comparison import FileComparison, Segment
from services.profiling import ProfilingSummary

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


@file_comparison_bindable.field("isRenamedFile")
def resolve_is_renamed_file(file_comparison: FileComparison, info) -> bool:
    base_name = file_comparison.name["base"]
    head_name = file_comparison.name["head"]
    return base_name is not None and head_name is not None and base_name != head_name


@file_comparison_bindable.field("isDeletedFile")
def resolve_is_deleted_file(file_comparison: FileComparison, info) -> bool:
    base_name = file_comparison.name["base"]
    head_name = file_comparison.name["head"]
    return base_name is not None and head_name is None


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


@file_comparison_bindable.field("patchTotals")
def resolve_patch_percent_covered(
    file_comparison: FileComparison, info
) -> Optional[dict]:
    return file_comparison.totals["head"].diff


@file_comparison_bindable.field("segments")
@sync_to_async
def resolve_segments(file_comparison: FileComparison, info) -> List[Segment]:
    comparison = info.context["comparison"]

    # reinstantiate with the full source code so we can include
    # unintended coverage changes
    file_comparison = comparison.get_file_comparison(
        file_comparison.name["head"], with_src=True, bypass_max_diff=True
    )

    return file_comparison.segments


@file_comparison_bindable.field("isCriticalFile")
@sync_to_async
def resolve_is_critical_file(file_comparison: FileComparison, info) -> bool:
    if "profiling_summary" in info.context:
        base_name = file_comparison.name["base"]
        head_name = file_comparison.name["head"]

        profiling_summary: ProfilingSummary = info.context["profiling_summary"]
        critical_filenames = profiling_summary.critical_filenames

        return base_name in critical_filenames or head_name in critical_filenames

    return False
