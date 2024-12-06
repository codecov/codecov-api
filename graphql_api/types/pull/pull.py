from typing import Any, Optional, Union

import sentry_sdk
from ariadne import ObjectType
from graphql import GraphQLResolveInfo

from codecov.db import sync_to_async
from codecov_auth.models import Owner
from compare.models import CommitComparison
from core.models import Commit, Pull
from graphql_api.actions.commits import pull_commits
from graphql_api.actions.comparison import validate_commit_comparison
from graphql_api.dataloader.bundle_analysis import load_bundle_analysis_comparison
from graphql_api.dataloader.commit import CommitLoader
from graphql_api.dataloader.comparison import ComparisonLoader
from graphql_api.dataloader.owner import OwnerLoader
from graphql_api.helpers.connection import Connection, queryset_to_connection_sync
from graphql_api.types.comparison.comparison import (
    FirstPullRequest,
    MissingBaseCommit,
    MissingHeadCommit,
)
from graphql_api.types.enums import OrderingDirection, PullRequestState
from services.bundle_analysis import BundleAnalysisComparison
from services.comparison import ComparisonReport, PullRequestComparison

pull_bindable = ObjectType("Pull")

pull_bindable.set_alias("pullId", "pullid")


@pull_bindable.field("state")
def resolve_state(pull: Pull, info: GraphQLResolveInfo) -> PullRequestState:
    return PullRequestState(pull.state)


@pull_bindable.field("author")
def resolve_author(pull: Pull, info: GraphQLResolveInfo) -> Optional[Owner]:
    if pull.author_id:
        return OwnerLoader.loader(info).load(pull.author_id)


@pull_bindable.field("head")
def resolve_head(pull: Pull, info: GraphQLResolveInfo) -> Optional[Commit]:
    if pull.head is None:
        return None
    return CommitLoader.loader(info, pull.repository_id).load(pull.head)


@pull_bindable.field("comparedTo")
def resolve_base(pull: Pull, info: GraphQLResolveInfo) -> Optional[Commit]:
    if pull.compared_to is None:
        return None
    return CommitLoader.loader(info, pull.repository_id).load(pull.compared_to)


@sync_to_async
def is_first_pull_request(pull: Pull) -> bool:
    return pull.repository.pull_requests.order_by("id").first() == pull


@sentry_sdk.trace
@pull_bindable.field("compareWithBase")
async def resolve_compare_with_base(
    pull: Pull, info: GraphQLResolveInfo, **kwargs: Any
) -> Union[CommitComparison, Any]:
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


@sentry_sdk.trace
@pull_bindable.field("bundleAnalysisCompareWithBase")
@sync_to_async
def resolve_bundle_analysis_compare_with_base(
    pull: Pull, info: GraphQLResolveInfo, **kwargs: Any
) -> Union[BundleAnalysisComparison, Any]:
    if not pull.compared_to:
        if pull.repository.pull_requests.order_by("id").first() == pull:
            return FirstPullRequest()
        else:
            return MissingBaseCommit()

    # Handles a case where the PR was created without any uploads because all bundles
    # from the build are cached. Instead of showing a "no commit error" we will instead
    # show the parent bundle report as it implies everything was cached and carried
    # over to the head commit
    head_commit_sha = pull.head if pull.head else pull.compared_to

    bundle_analysis_comparison = load_bundle_analysis_comparison(
        Commit.objects.filter(
            commitid=pull.compared_to, repository=pull.repository
        ).first(),
        Commit.objects.filter(
            commitid=head_commit_sha, repository=pull.repository
        ).first(),
    )

    # Store the created SQLite DB path in info.context
    # when the request is fully handled, have the file deleted
    if isinstance(bundle_analysis_comparison, BundleAnalysisComparison):
        info.context[
            "request"
        ].bundle_analysis_base_report_db_path = (
            bundle_analysis_comparison.comparison.base_report.db_path
        )
        info.context[
            "request"
        ].bundle_analysis_head_report_db_path = (
            bundle_analysis_comparison.comparison.head_report.db_path
        )

    return bundle_analysis_comparison


@pull_bindable.field("commits")
@sync_to_async
def resolve_commits(pull: Pull, info: GraphQLResolveInfo, **kwargs: Any) -> Connection:
    queryset = pull_commits(pull)

    return queryset_to_connection_sync(
        queryset,
        ordering=("timestamp",),
        ordering_direction=OrderingDirection.DESC,
        **kwargs,
    )


@pull_bindable.field("behindBy")
def resolve_behind_by(pull: Pull, info: GraphQLResolveInfo, **kwargs: Any) -> int:
    return pull.behind_by


@pull_bindable.field("behindByCommit")
def resolve_behind_by_commit(
    pull: Pull, info: GraphQLResolveInfo, **kwargs: Any
) -> str:
    return pull.behind_by_commit


@pull_bindable.field("firstPull")
@sync_to_async
def resolve_first_pull(pull: Pull, info: GraphQLResolveInfo) -> bool:
    # returns true if this pull is/was the 1st for a repo
    return pull.repository.pull_requests.order_by("id").first() == pull
