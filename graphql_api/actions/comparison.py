from codecov.db import sync_to_async
from services.comparison import PullRequestComparison


@sync_to_async
def validate_comparison(comparison: PullRequestComparison):
    comparison.validate()
