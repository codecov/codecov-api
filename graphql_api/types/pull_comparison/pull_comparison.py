from ariadne import ObjectType
from asgiref.sync import sync_to_async

from services.comparison import PullRequestComparison

pull_comparison_bindable = ObjectType("PullComparison")


@pull_comparison_bindable.field("fileComparisons")
@sync_to_async
def resolve_file_comparisons(pull_comparison: PullRequestComparison, info):
    # `files` returns a generator that yields lazily
    # use `list` here to force evaluation while we're in a sync context
    return list(pull_comparison.files)


@pull_comparison_bindable.field("baseTotals")
@sync_to_async
def resolve_base_totals(pull_comparison: PullRequestComparison, info):
    return pull_comparison.totals["base"]


@pull_comparison_bindable.field("headTotals")
@sync_to_async
def resolve_head_totals(pull_comparison: PullRequestComparison, info):
    return pull_comparison.totals["base"]
