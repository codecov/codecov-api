import enum
from dataclasses import dataclass
from typing import List, Optional

from ariadne import ObjectType, UnionType, convert_kwargs_to_snake_case
from asgiref.sync import sync_to_async

import services.components as components_service
from compare.models import CommitComparison, FlagComparison
from graphql_api.actions.flags import get_flag_comparisons
from graphql_api.types.errors import (
    MissingBaseCommit,
    MissingBaseReport,
    MissingComparison,
    MissingHeadCommit,
    MissingHeadReport,
)
from services.comparison import ComparisonReport, ImpactedFile, PullRequestComparison
from services.components import ComponentComparison

comparison_bindable = ObjectType("Comparison")


@comparison_bindable.field("impactedFiles")
@convert_kwargs_to_snake_case
@sync_to_async
def resolve_impacted_files(
    comparison: CommitComparison, info, filters=None
) -> List[ImpactedFile]:
    command = info.context["executor"].get_command("compare")
    return command.fetch_impacted_files(comparison, filters)


@comparison_bindable.field("impactedFilesCount")
@sync_to_async
def resolve_impacted_files_count(comparison: CommitComparison, info):
    comparison_report = ComparisonReport(comparison)
    return len(comparison_report.impacted_files)


@comparison_bindable.field("directChangedFilesCount")
@sync_to_async
def resolve_impacted_files_count(comparison: CommitComparison, info):
    comparison_report = ComparisonReport(comparison)
    return len(comparison_report.impacted_files_with_direct_changes)


@comparison_bindable.field("indirectChangedFilesCount")
@sync_to_async
def resolve_impacted_files_count(comparison: CommitComparison, info):
    comparison_report = ComparisonReport(comparison)
    return len(comparison_report.impacted_files_with_unintended_changes)


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


# TODO: get rid of validate here, headTotals and hasDifferentNumberOfHeadAndBaseReports as there is a
# validate call a resolver above
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


@comparison_bindable.field("patchTotals")
def resolve_patch_totals(comparison: CommitComparison, info):
    totals = comparison.patch_totals
    if not totals:
        return None

    coverage = totals["coverage"]
    if coverage is not None:
        # we always return `coverage` as a percentage but it's stored
        # in the database as 0 <= value <= 1
        coverage *= 100

    return {**totals, "coverage": coverage}


@comparison_bindable.field("flagComparisons")
@sync_to_async
def resolve_flag_comparisons(comparison, info) -> List[FlagComparison]:
    return list(get_flag_comparisons(comparison))


@comparison_bindable.field("componentComparisons")
@sync_to_async
def resolve_component_comparisons(
    comparison: CommitComparison, info
) -> Optional[List[ComponentComparison]]:
    user = info.context["request"].user

    if "comparison" not in info.context:
        return None

    comparison = info.context["comparison"]
    components = components_service.commit_components(comparison.head_commit, user)
    return [ComponentComparison(comparison, component) for component in components]


"""
    Resolver to return if the head and base of a pull request have
    different number of reports on the head and base. This implementation
    excludes commits that have carried forward sessions.
"""


@comparison_bindable.field("flagComparisonsCount")
@sync_to_async
def resolve_flag_comparisons_count(comparison, info):
    return get_flag_comparisons(comparison).count()


@comparison_bindable.field("hasDifferentNumberOfHeadAndBaseReports")
@sync_to_async
def resolve_has_different_number_of_head_and_base_reports(
    comparison: CommitComparison, info, **kwargs
) -> int:
    # Ensure PullRequestComparison type exists in context
    if "comparison" not in info.context:
        return False

    comparison: PullRequestComparison = info.context["comparison"]
    return comparison.has_different_number_of_head_and_base_sessions


comparison_result_bindable = UnionType("ComparisonResult")


@comparison_result_bindable.type_resolver
def resolve_comparison_result_type(obj, *_):
    if isinstance(obj, CommitComparison):
        return "Comparison"
    elif isinstance(obj, MissingBaseCommit):
        return "MissingBaseCommit"
    elif isinstance(obj, MissingHeadCommit):
        return "MissingHeadCommit"
    elif isinstance(obj, MissingComparison):
        return "MissingComparison"
    elif isinstance(obj, MissingBaseReport):
        return "MissingBaseReport"
    elif isinstance(obj, MissingHeadReport):
        return "MissingHeadReport"
