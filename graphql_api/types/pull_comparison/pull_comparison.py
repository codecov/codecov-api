from typing import List

from ariadne import ObjectType
from asgiref.sync import sync_to_async

from services.comparison import FileComparison, PullRequestComparison

pull_comparison_bindable = ObjectType("PullComparison")


@pull_comparison_bindable.field("files")
@sync_to_async
def resolve_file_comparisons(
    pull_comparison: PullRequestComparison, info
) -> List[FileComparison]:
    return [file for file in pull_comparison.files if file.has_diff]


@pull_comparison_bindable.field("baseTotals")
@sync_to_async
def resolve_base_totals(pull_comparison: PullRequestComparison, info) -> dict:
    return pull_comparison.totals["base"]


@pull_comparison_bindable.field("headTotals")
@sync_to_async
def resolve_head_totals(pull_comparison: PullRequestComparison, info) -> dict:
    return pull_comparison.totals["head"]
