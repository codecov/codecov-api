from ariadne import ObjectType

from codecov.db import sync_to_async
from compare.models import CommitComparison
from core.models import Pull
from graphql_api.actions.commits import pull_commits
from graphql_api.actions.comparison import validate_comparison
from graphql_api.dataloader.commit import CommitLoader
from graphql_api.dataloader.comparison import ComparisonLoader
from graphql_api.dataloader.owner import OwnerLoader
from graphql_api.helpers.connection import queryset_to_connection_sync
from graphql_api.types.comparison.comparison import (
    MissingBaseCommit,
    MissingBaseReport,
    MissingComparison,
    MissingHeadCommit,
    MissingHeadReport,
)
from graphql_api.types.enums import OrderingDirection, PullRequestState
from services.comparison import (
    ComparisonReport,
    MissingComparisonReport,
    PullRequestComparison,
)

pull_bindable = ObjectType("Pull")

pull_bindable.set_alias("pullId", "pullid")


@pull_bindable.field("state")
def resolve_state(pull, info):
    return PullRequestState(pull.state)


@pull_bindable.field("author")
def resolve_author(pull, info):
    if pull.author_id:
        return OwnerLoader.loader(info).load(pull.author_id)


@pull_bindable.field("head")
def resolve_head(pull, info):
    if pull.head == None:
        return None
    return CommitLoader.loader(info, pull.repository_id).load(pull.head)


@pull_bindable.field("comparedTo")
def resolve_base(pull, info):
    if pull.compared_to == None:
        return None
    return CommitLoader.loader(info, pull.repository_id).load(pull.compared_to)


@pull_bindable.field("compareWithBaseTemp")
async def resolve_compare_with_base(pull, info, **kwargs):
    if not pull.compared_to or not pull.head:
        return None

    comparison_loader = ComparisonLoader.loader(info, pull.repository_id)
    commit_comparison = await comparison_loader.load((pull.compared_to, pull.head))

    if commit_comparison and commit_comparison.is_processed:
        user = info.context["request"].user
        comparison = PullRequestComparison(user, pull)

        # store the comparison in the context - to be used in the `Comparison` resolvers
        info.context["comparison"] = comparison

    return commit_comparison


@pull_bindable.field("compareWithBase")
async def resolve_compare_with_base(pull, info, **kwargs):
    if not pull.compared_to:
        return MissingBaseCommit()
    if not pull.head:
        return MissingHeadCommit()

    comparison_loader = ComparisonLoader.loader(info, pull.repository_id)
    commit_comparison = await comparison_loader.load((pull.compared_to, pull.head))

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

    if commit_comparison and commit_comparison.is_processed:
        user = info.context["request"].user
        comparison = PullRequestComparison(user, pull)

        # Preemptively validate the comparison object before storing it in context as a commit_comparison can
        # be successful but still have errors w/ the head+base report
        try:
            await validate_comparison(comparison)
        except MissingComparisonReport as e:
            (error_message) = str(e)
            if error_message == "Missing head report":
                return MissingHeadReport()
            if error_message == "Missing base report":
                return MissingBaseReport()
        # store the comparison in the context - to be used in the `Comparison` resolvers
        info.context["comparison"] = comparison

    return ComparisonReport(commit_comparison)


@pull_bindable.field("commits")
@sync_to_async
def resolve_commits(pull: Pull, info, **kwargs):
    queryset = pull_commits(pull)

    return queryset_to_connection_sync(
        queryset,
        ordering=("timestamp",),
        ordering_direction=OrderingDirection.DESC,
        **kwargs,
    )
