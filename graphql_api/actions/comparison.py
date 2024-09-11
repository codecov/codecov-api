from typing import Optional, Union

from compare.models import CommitComparison
from graphql_api.types.comparison.comparison import (
    MissingBaseReport,
    MissingComparison,
    MissingHeadReport,
)


def validate_commit_comparison(
    commit_comparison: Optional[CommitComparison],
) -> Union[MissingBaseReport, MissingHeadReport, MissingComparison]:
    if not commit_comparison:
        return MissingComparison()

    if (
        commit_comparison.error
        == CommitComparison.CommitComparisonErrors.MISSING_BASE_REPORT.value
    ):
        return MissingBaseReport()

    if (
        commit_comparison.error
        == CommitComparison.CommitComparisonErrors.MISSING_HEAD_REPORT.value
    ):
        return MissingHeadReport()

    if commit_comparison.state == CommitComparison.CommitComparisonStates.ERROR:
        return MissingComparison()
