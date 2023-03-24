from typing import Union

from codecov.db import sync_to_async
from compare.models import CommitComparison
from graphql_api.types.comparison.comparison import (
    MissingBaseReport,
    MissingComparison,
    MissingHeadReport,
)
from services.comparison import Comparison, PullRequestComparison


@sync_to_async
def validate_comparison(comparison: Union[PullRequestComparison, Comparison]):
    comparison.validate()


def validate_commit_comparison(commit_comparison: CommitComparison):
    if not commit_comparison:
        return (False, MissingComparison())

    if (
        commit_comparison.error
        == CommitComparison.CommitComparisonErrors.MISSING_BASE_REPORT.value
    ):
        return (False, MissingBaseReport())

    if (
        commit_comparison.error
        == CommitComparison.CommitComparisonErrors.MISSING_HEAD_REPORT.value
    ):
        return (False, MissingHeadReport())

    if commit_comparison.state == CommitComparison.CommitComparisonStates.ERROR:
        return (False, MissingComparison())

    return (True, None)
