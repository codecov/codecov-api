from ariadne import ObjectType

from codecov.db import sync_to_async
from core.models import Pull
from graphql_api.actions.commits import pull_commits
from graphql_api.actions.comparison import validate_commit_comparison
from graphql_api.dataloader.commit import CommitLoader
from graphql_api.dataloader.comparison import ComparisonLoader
from graphql_api.dataloader.owner import OwnerLoader
from graphql_api.helpers.connection import queryset_to_connection_sync
from graphql_api.types.comparison.comparison import MissingBaseCommit, MissingHeadCommit
from graphql_api.types.enums import OrderingDirection, PullRequestState
from services.comparison import ComparisonReport, PullRequestComparison

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
async def resolve_compare_with_base_temp(pull, info, **kwargs):
    if not pull.compared_to or not pull.head:
        return None

    comparison_loader = ComparisonLoader.loader(info, pull.repository_id)
    commit_comparison = await comparison_loader.load((pull.compared_to, pull.head))

    if commit_comparison and commit_comparison.is_processed:
        user = info.context["request"].user
        comparison = PullRequestComparison(user, pull)

        # store the comparison in the context - to be used in the `Comparison` resolvers
        info.context["comparison"] = comparison

    if commit_comparison:
        return ComparisonReport(commit_comparison)


@pull_bindable.field("compareWithBase")
async def resolve_compare_with_base(pull, info, **kwargs):
    if not pull.compared_to:
        return MissingBaseCommit()
    if not pull.head:
        return MissingHeadCommit()

    comparison_loader = ComparisonLoader.loader(info, pull.repository_id)
    commit_comparison = await comparison_loader.load((pull.compared_to, pull.head))

    comparison_error = validate_commit_comparison(commit_comparison=commit_comparison)

    if comparison_error:
        return comparison_error

    if commit_comparison and commit_comparison.is_processed:
        user = info.context["request"].user
        comparison = PullRequestComparison(user, pull)
        # store the comparison in the context - to be used in the `Comparison` resolvers
        info.context["comparison"] = comparison

    if commit_comparison:
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


@pull_bindable.field("behindBy")
def resolve_behind_by(pull: Pull, info, **kwargs) -> int:
    return pull.behind_by


@pull_bindable.field("behindByCommit")
def resolve_behind_by_commit(pull: Pull, info, **kwargs) -> str:
    return pull.behind_by_commit
