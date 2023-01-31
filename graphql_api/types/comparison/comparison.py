from typing import List, Optional

from ariadne import ObjectType, UnionType, convert_kwargs_to_snake_case
from asgiref.sync import sync_to_async

import services.components as components_service
from compare.models import FlagComparison
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


@comparison_bindable.field("state")
def resolve_state(comparison: ComparisonReport, info) -> str:
    return comparison.commit_comparison.state


@comparison_bindable.field("impactedFiles")
@convert_kwargs_to_snake_case
@sync_to_async
def resolve_impacted_files(
    comparison: ComparisonReport, info, filters=None
) -> List[ImpactedFile]:
    command = info.context["executor"].get_command("compare")
    return command.fetch_impacted_files(comparison, filters)


@comparison_bindable.field("impactedFilesCount")
@sync_to_async
def resolve_impacted_files_count(comparison: ComparisonReport, info):
    return len(comparison.impacted_files)


@comparison_bindable.field("directChangedFilesCount")
@sync_to_async
def resolve_direct_changed_files_count(comparison: CommitComparison, info):
    comparison_report = ComparisonReport(comparison)
    return len(comparison_report.impacted_files_with_direct_changes)


@comparison_bindable.field("indirectChangedFilesCount")
@sync_to_async
def resolve_indirect_changed_files_count(comparison: ComparisonReport, info):
    return len(comparison.impacted_files_with_unintended_changes)


@comparison_bindable.field("impactedFile")
@sync_to_async
def resolve_impacted_file(comparison: ComparisonReport, info, path) -> ImpactedFile:
    return comparison.impacted_file(path)


# TODO: rename `changeCoverage`
@comparison_bindable.field("changeWithParent")
def resolve_change_with_parent(comparison: ComparisonReport, info):
    # TODO: can we get this from the `ComparisonReport` instead?
    command = info.context["executor"].get_command("compare")
    return command.change_with_parent(comparison.commit_comparison)


@comparison_bindable.field("baseTotals")
@sync_to_async
def resolve_base_totals(comparison: ComparisonReport, info):
    if "comparison" not in info.context:
        return None

    comparison = info.context["comparison"]
    return comparison.totals["base"]


@comparison_bindable.field("headTotals")
@sync_to_async
def resolve_head_totals(comparison: ComparisonReport, info):
    if "comparison" not in info.context:
        return None

    comparison = info.context["comparison"]
    return comparison.totals["head"]


@comparison_bindable.field("patchTotals")
def resolve_patch_totals(comparison: ComparisonReport, info):
    totals = comparison.commit_comparison.patch_totals
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
def resolve_flag_comparisons(
    comparison: ComparisonReport, info
) -> List[FlagComparison]:
    return list(get_flag_comparisons(comparison.commit_comparison))


@comparison_bindable.field("componentComparisons")
@sync_to_async
def resolve_component_comparisons(
    comparison: ComparisonReport, info
) -> Optional[List[ComponentComparison]]:
    user = info.context["request"].user

    if "comparison" not in info.context:
        return None

    comparison = info.context["comparison"]
    components = components_service.commit_components(comparison.head_commit, user)
    return [ComponentComparison(comparison, component) for component in components]


@comparison_bindable.field("flagComparisonsCount")
@sync_to_async
def resolve_flag_comparisons_count(comparison: ComparisonReport, info):
    """
    Resolver to return if the head and base of a pull request have
    different number of reports on the head and base. This implementation
    excludes commits that have carried forward sessions.
    """
    return get_flag_comparisons(comparison.commit_comparison).count()


@comparison_bindable.field("hasDifferentNumberOfHeadAndBaseReports")
@sync_to_async
def resolve_has_different_number_of_head_and_base_reports(
    comparison: ComparisonReport, info, **kwargs
) -> int:
    # Ensure PullRequestComparison type exists in context
    if "comparison" not in info.context:
        return False

    comparison: PullRequestComparison = info.context["comparison"]
    return comparison.has_different_number_of_head_and_base_sessions


comparison_result_bindable = UnionType("ComparisonResult")


@comparison_result_bindable.type_resolver
def resolve_comparison_result_type(obj, *_):
    if isinstance(obj, ComparisonReport):
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
