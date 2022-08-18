from typing import List, Optional

from ariadne import ObjectType
from asgiref.sync import sync_to_async

from compare.models import CommitComparison, FlagComparison
from graphql_api.actions.flags import get_flag_comparisons
from services.comparison import ComparisonReport, ImpactedFile

comparison_bindable = ObjectType("Comparison")


@comparison_bindable.field("impactedFiles")
@sync_to_async
def resolve_impacted_files(
    comparison: CommitComparison, info, filters={}
) -> List[ImpactedFile]:
    comparison_report = ComparisonReport(comparison)
    return comparison_report.impacted_files(filters=filters)


@comparison_bindable.field("impactedFile")
@sync_to_async
def resolve_impacted_file(comparison: CommitComparison, info, path) -> ImpactedFile:
    comparison_report = ComparisonReport(comparison)
    return comparison_report.impacted_file(path)


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
    comparison.validate()
    return [file for file in comparison.files if file.has_diff or file.has_changes]


@comparison_bindable.field("baseTotals")
@sync_to_async
def resolve_base_totals(comparison, info):
    if "comparison" not in info.context:
        return None

    comparison = info.context["comparison"]
    comparison.validate()
    return comparison.totals["base"]


@comparison_bindable.field("headTotals")
@sync_to_async
def resolve_head_totals(comparison, info):
    if "comparison" not in info.context:
        return None

    comparison = info.context["comparison"]
    comparison.validate()
    return comparison.totals["head"]


@comparison_bindable.field("flagComparisons")
@sync_to_async
def resolve_flag_comparisons(comparison, info) -> List[FlagComparison]:
    return list(get_flag_comparisons(comparison))
