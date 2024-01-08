from ariadne import ObjectType
from asgiref.sync import async_to_sync

from codecov.db import sync_to_async
from core.models import Commit, Pull
from graphql_api.actions.commits import pull_commits
from graphql_api.actions.comparison import validate_commit_comparison
from graphql_api.dataloader.bundle_analysis import load_bundle_analysis_comparison
from graphql_api.dataloader.commit import CommitLoader
from graphql_api.dataloader.comparison import ComparisonLoader
from graphql_api.dataloader.owner import OwnerLoader
from graphql_api.helpers.connection import queryset_to_connection_sync
from graphql_api.types.comparison.comparison import (
    FirstPullRequest,
    MissingBaseCommit,
    MissingHeadCommit,
)
from graphql_api.types.enums import OrderingDirection, PullRequestState
from services.comparison import ComparisonReport, PullRequestComparison

pull_bindable = ObjectType("Pull")

pull_bindable.set_alias("pullId", "pullid")


@pull_bindable.field("state")
def resolve_state(pull, info) -> PullRequestState:
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


@sync_to_async
def is_first_pull_request(pull: Pull):
    return pull.repository.pull_requests.order_by("id").first() == pull


@pull_bindable.field("compareWithBase")
async def resolve_compare_with_base(pull, info, **kwargs):
    if not pull.compared_to:
        if await is_first_pull_request(pull):
            return FirstPullRequest()
        else:
            return MissingBaseCommit()
    if not pull.head:
        return MissingHeadCommit()

    comparison_loader = ComparisonLoader.loader(info, pull.repository_id)
    commit_comparison = await comparison_loader.load((pull.compared_to, pull.head))

    comparison_error = validate_commit_comparison(commit_comparison=commit_comparison)

    if comparison_error:
        return comparison_error

    if commit_comparison and commit_comparison.is_processed:
        current_owner = info.context["request"].current_owner
        comparison = PullRequestComparison(current_owner, pull)
        # store the comparison in the context - to be used in the `Comparison` resolvers
        info.context["comparison"] = comparison

    if commit_comparison:
        return ComparisonReport(commit_comparison)


@pull_bindable.field("bundleAnalysisCompareWithBase")
@sync_to_async
def resolve_bundle_analysis_compare_with_base(pull, info, **kwargs):
    if not pull.compared_to:
        if is_first_pull_request(pull):
            return FirstPullRequest()
        else:
            return MissingBaseCommit()
    if not pull.head:
        return MissingHeadCommit()

    base_commit = Commit.objects.filter(commitid=pull.compared_to).first()
    if not base_commit:
        return MissingBaseCommit()
    head_commit = Commit.objects.filter(commitid=pull.head).first()
    if not head_commit:
        return MissingHeadCommit()

    return load_bundle_analysis_comparison(base_commit, head_commit)


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


@pull_bindable.field("behindBy")
def resolve_behind_by(pull: Pull, info, **kwargs) -> int:
    return pull.behind_by


@pull_bindable.field("behindByCommit")
def resolve_behind_by_commit(pull: Pull, info, **kwargs) -> str:
    return pull.behind_by_commit


@pull_bindable.field("firstPull")
@sync_to_async
def resolve_first_pull(pull: Pull, info) -> bool:
    # returns true if this pull is/was the 1st for a repo
    return pull.repository.pull_requests.order_by("id").first() == pull
