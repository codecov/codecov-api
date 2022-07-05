from typing import List

from ariadne import ObjectType
from asgiref.sync import sync_to_async

from compare.models import CommitComparison, FlagComparison

comparison_bindable = ObjectType("Comparison")


@comparison_bindable.field("impactedFiles")
def resolve_impacted_files(comparison, info):
    command = info.context["executor"].get_command("compare")
    return command.get_impacted_files(comparison)


@comparison_bindable.field("changeWithParent")
def resolve_change_with_parent(comparison, info):
    command = info.context["executor"].get_command("compare")
    return command.change_with_parent(comparison)


@comparison_bindable.field("fileComparisons")
@sync_to_async
def resolve_file_comparisons(comparison, info):
    if "comparison" not in info.context:
        return None

    comparison = info.context["comparison"]
    return [file for file in comparison.files if file.has_diff or file.has_changes]


@comparison_bindable.field("baseTotals")
@sync_to_async
def resolve_base_totals(comparison, info):
    if "comparison" not in info.context:
        return None

    comparison = info.context["comparison"]
    return comparison.totals["base"]


@comparison_bindable.field("headTotals")
@sync_to_async
def resolve_head_totals(comparison, info):
    if "comparison" not in info.context:
        return None

    comparison = info.context["comparison"]
    return comparison.totals["head"]


@comparison_bindable.field("flagComparisons")
@sync_to_async
def resolve_flag_comparisons(comparison, info) -> List[FlagComparison]:
    if "comparison" not in info.context:
        return None

    comparison = info.context["comparison"]
    commit_comparison = CommitComparison.objects.filter(
        base_commit=comparison.base_commit, compare_commit=comparison.head_commit
    ).first()

    if not commit_comparison:
        return None

    flag_comparisons = (
        FlagComparison.objects.select_related("repositoryflag")
        .filter(commit_comparison=commit_comparison.id)
        .all()
    )

    if not flag_comparisons:
        return []

    return flag_comparisons
