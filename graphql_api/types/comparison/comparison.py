import asyncio

from ariadne import ObjectType

from graphql_api.dataloader.commit_report import CommitReportLoader

comparison_bindable = ObjectType("Comparison")


@comparison_bindable.field("impactedFiles")
def resolve_impacted_files(comparison, info):
    command = info.context["executor"].get_command("compare")
    return command.get_impacted_files(comparison)


@comparison_bindable.field("changeWithParent")
async def resolve_change_with_parent(comparison, info):
    loader = CommitReportLoader.loader(info)

    compare_commit_report, base_commit_report = await asyncio.gather(
        loader.load(comparison.compare_commit_id),
        loader.load(comparison.base_commit_id),
    )

    if compare_commit_report is not None and base_commit_report is not None:
        compare_commit_totals = compare_commit_report.reportleveltotals
        base_commit_totals = base_commit_report.reportleveltotals
        if (
            compare_commit_totals is not None
            and hasattr(compare_commit_totals, "coverage")
            and base_commit_totals is not None
            and hasattr(base_commit_totals, "coverage")
        ):
            return compare_commit_totals.coverage - base_commit_totals.coverage
