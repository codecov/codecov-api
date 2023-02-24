from asyncio import gather
from typing import List, Optional

from ariadne import ObjectType, UnionType, convert_kwargs_to_snake_case

import services.components as components_service
from codecov.db import sync_to_async
from compare.models import FlagComparison
from graphql_api.actions.flags import get_flag_comparisons
from graphql_api.dataloader.commit import CommitLoader
from graphql_api.types.errors import (
    MissingBaseCommit,
    MissingBaseReport,
    MissingComparison,
    MissingHeadCommit,
    MissingHeadReport,
)
from reports.models import ReportLevelTotals
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
def resolve_direct_changed_files_count(comparison: ComparisonReport, info):
    return len(comparison.impacted_files_with_direct_changes)


@comparison_bindable.field("indirectChangedFilesCount")
@sync_to_async
def resolve_indirect_changed_files_count(comparison: ComparisonReport, info):
    return len(comparison.impacted_files_with_unintended_changes)


@comparison_bindable.field("impactedFile")
@sync_to_async
def resolve_impacted_file(comparison: ComparisonReport, info, path) -> ImpactedFile:
    return comparison.impacted_file(path)


# TODO: rename `changeCoverage`
@comparison_bindable.field("changeCoverage")
async def resolve_change_coverage(
    comparison: ComparisonReport, info
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
    if base_commit and base_commit.commitreport:
        base_totals = base_commit.commitreport.reportleveltotals
    if head_commit and head_commit.commitreport:
        head_totals = head_commit.commitreport.reportleveltotals

    if base_totals and head_totals:
        return head_totals.coverage - base_totals.coverage


# deprecated field
comparison_bindable.set_field("changeWithParent", resolve_change_coverage)


@comparison_bindable.field("baseTotals")
async def resolve_base_totals(
    comparison: ComparisonReport, info
) -> Optional[ReportLevelTotals]:
    repository_id = comparison.commit_comparison.base_commit.repository_id
    loader = CommitLoader.loader(info, repository_id)

    # the loader prefetches everything we need to get the totals
    base_commit = await loader.load(comparison.commit_comparison.base_commit.commitid)
    if base_commit and base_commit.commitreport:
        return base_commit.commitreport.reportleveltotals


@comparison_bindable.field("headTotals")
async def resolve_head_totals(
    comparison: ComparisonReport, info
) -> Optional[ReportLevelTotals]:
    repository_id = comparison.commit_comparison.compare_commit.repository_id
    loader = CommitLoader.loader(info, repository_id)

    # the loader prefetches everything we need to get the totals
    head_commit = await loader.load(
        comparison.commit_comparison.compare_commit.commitid
    )
    if head_commit and head_commit.commitreport:
        return head_commit.commitreport.reportleveltotals


@comparison_bindable.field("patchTotals")
def resolve_patch_totals(comparison: ComparisonReport, info) -> dict:
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
    head_commit = comparison.commit_comparison.compare_commit
    components = components_service.commit_components(head_commit, user)

    # TODO: can we change this to not rely on the comparison in the context?
    if not "comparison" in info.context:
        return None
    comparison = info.context["comparison"]
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
    # TODO: can we remove the need for `info.context["conmparison"]` here?

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
