from asyncio import gather
from typing import List, Optional

import sentry_sdk
from ariadne import ObjectType, UnionType
from graphql.type.definition import GraphQLResolveInfo

import services.components as components_service
from codecov.db import sync_to_async
from compare.commands.compare.compare import CompareCommands
from compare.models import ComponentComparison, FlagComparison
from graphql_api.actions.flags import get_flag_comparisons
from graphql_api.dataloader.commit import CommitLoader
from graphql_api.types.errors import (
    MissingBaseCommit,
    MissingBaseReport,
    MissingComparison,
    MissingHeadCommit,
    MissingHeadReport,
)
from graphql_api.types.errors.errors import UnknownFlags
from reports.models import ReportLevelTotals
from services.comparison import (
    Comparison,
    ComparisonReport,
    FirstPullRequest,
    ImpactedFile,
)

comparison_bindable = ObjectType("Comparison")


@comparison_bindable.field("state")
def resolve_state(comparison: ComparisonReport, info: GraphQLResolveInfo) -> str:
    return comparison.commit_comparison.state


@comparison_bindable.field("impactedFiles")
@sync_to_async
def resolve_impacted_files(
    comparison_report: ComparisonReport, info: GraphQLResolveInfo, filters=None
) -> List[ImpactedFile]:
    command: CompareCommands = info.context["executor"].get_command("compare")
    comparison: Comparison = info.context.get("comparison", None)

    if filters and comparison:
        flags = filters.get("flags", [])
        if flags and set(flags).isdisjoint(set(comparison.head_report.flags)):
            return UnknownFlags()

    return {
        "results": command.fetch_impacted_files(comparison_report, comparison, filters)
    }


@comparison_bindable.field("impactedFilesCount")
@sync_to_async
def resolve_impacted_files_count(
    comparison: ComparisonReport, info: GraphQLResolveInfo
):
    return len(comparison.impacted_files)


@comparison_bindable.field("directChangedFilesCount")
@sync_to_async
def resolve_direct_changed_files_count(
    comparison: ComparisonReport, info: GraphQLResolveInfo
):
    return len(comparison.impacted_files_with_direct_changes)


@comparison_bindable.field("indirectChangedFilesCount")
@sync_to_async
def resolve_indirect_changed_files_count(
    comparison: ComparisonReport, info: GraphQLResolveInfo
):
    return len(comparison.impacted_files_with_unintended_changes)


@comparison_bindable.field("impactedFile")
@sync_to_async
def resolve_impacted_file(
    comparison: ComparisonReport, info: GraphQLResolveInfo, path
) -> ImpactedFile:
    return comparison.impacted_file(path)


# TODO: rename `changeCoverage`
@comparison_bindable.field("changeCoverage")
async def resolve_change_coverage(
    comparison: ComparisonReport, info: GraphQLResolveInfo
) -> Optional[float]:
    repository_id = comparison.commit_comparison.compare_commit.repository_id
    loader = CommitLoader.loader(info, repository_id)

    # the loader prefetches everything we need to get the totals
    base_commit, head_commit = await gather(
        loader.load(comparison.commit_comparison.base_commit.commitid),
        loader.load(comparison.commit_comparison.compare_commit.commitid),
    )

    base_totals = None
    head_totals = None
    if (
        base_commit
        and base_commit.commitreport
        and hasattr(base_commit.commitreport, "reportleveltotals")
    ):
        base_totals = base_commit.commitreport.reportleveltotals
    if (
        head_commit
        and head_commit.commitreport
        and hasattr(head_commit.commitreport, "reportleveltotals")
    ):
        head_totals = head_commit.commitreport.reportleveltotals

    if base_totals and head_totals:
        return head_totals.coverage - base_totals.coverage


@comparison_bindable.field("baseTotals")
async def resolve_base_totals(
    comparison: ComparisonReport, info: GraphQLResolveInfo
) -> Optional[ReportLevelTotals]:
    repository_id = comparison.commit_comparison.base_commit.repository_id
    loader = CommitLoader.loader(info, repository_id)

    # the loader prefetches everything we need to get the totals
    base_commit = await loader.load(comparison.commit_comparison.base_commit.commitid)
    if (
        base_commit
        and base_commit.commitreport
        and hasattr(base_commit.commitreport, "reportleveltotals")
    ):
        return base_commit.commitreport.reportleveltotals


@comparison_bindable.field("headTotals")
async def resolve_head_totals(
    comparison: ComparisonReport, info: GraphQLResolveInfo
) -> Optional[ReportLevelTotals]:
    repository_id = comparison.commit_comparison.compare_commit.repository_id
    loader = CommitLoader.loader(info, repository_id)

    # the loader prefetches everything we need to get the totals
    head_commit = await loader.load(
        comparison.commit_comparison.compare_commit.commitid
    )
    if (
        head_commit
        and head_commit.commitreport
        and hasattr(head_commit.commitreport, "reportleveltotals")
    ):
        return head_commit.commitreport.reportleveltotals


@sentry_sdk.trace
@comparison_bindable.field("patchTotals")
def resolve_patch_totals(
    comparison: ComparisonReport, info: GraphQLResolveInfo
) -> dict:
    totals = comparison.commit_comparison.patch_totals
    if not totals:
        return None

    coverage = totals["coverage"]
    if coverage is not None:
        # we always return `coverage` as a percentage but it's stored
        # in the database as 0 <= value <= 1
        coverage *= 100

    return {**totals, "coverage": coverage}


@sentry_sdk.trace
@comparison_bindable.field("flagComparisons")
@sync_to_async
def resolve_flag_comparisons(
    comparison: ComparisonReport, info: GraphQLResolveInfo, filters=None
) -> List[FlagComparison]:
    all_flags = get_flag_comparisons(comparison.commit_comparison)

    if filters and filters.get("term"):
        filtered_flags = [
            flag
            for flag in all_flags
            if filters["term"] in flag.repositoryflag.flag_name
        ]
        return filtered_flags

    return list(all_flags)


@sentry_sdk.trace
@comparison_bindable.field("componentComparisons")
@sync_to_async
def resolve_component_comparisons(
    comparison_report: ComparisonReport, info: GraphQLResolveInfo, filters=None
) -> List[ComponentComparison]:
    current_owner = info.context["request"].current_owner
    head_commit = comparison_report.commit_comparison.compare_commit
    components = components_service.commit_components(head_commit, current_owner)
    list_components = comparison_report.commit_comparison.component_comparisons.all()

    if filters and filters.get("components"):
        components = components_service.filter_components_by_name_or_id(
            components, filters["components"]
        )

        list_components = list_components.filter(
            component_id__in=[component.component_id for component in components]
        )

    # store for child resolvers (needed to get the component name, for example)
    info.context["components"] = {
        component.component_id: component for component in components
    }

    return list(list_components)


@comparison_bindable.field("componentComparisonsCount")
@sync_to_async
def resolve_component_comparisons_count(
    comparison_report: ComparisonReport, info: GraphQLResolveInfo
) -> int:
    return comparison_report.commit_comparison.component_comparisons.count()


@comparison_bindable.field("flagComparisonsCount")
@sync_to_async
def resolve_flag_comparisons_count(
    comparison: ComparisonReport, info: GraphQLResolveInfo
):
    """
    Resolver to return if the head and base of a pull request have
    different number of reports on the head and base. This implementation
    excludes commits that have carried forward sessions.
    """
    return get_flag_comparisons(comparison.commit_comparison).count()


@sentry_sdk.trace
@comparison_bindable.field("hasDifferentNumberOfHeadAndBaseReports")
@sync_to_async
def resolve_has_different_number_of_head_and_base_reports(
    comparison: ComparisonReport,
    info: GraphQLResolveInfo,
    **kwargs,  # type: ignore
) -> bool:
    # TODO: can we remove the need for `info.context["comparison"]` here?
    if "comparison" not in info.context:
        return False
    comparison: Comparison = info.context["comparison"]
    try:
        comparison.validate()
    except Exception:
        return False
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
    elif isinstance(obj, FirstPullRequest):
        return "FirstPullRequest"
