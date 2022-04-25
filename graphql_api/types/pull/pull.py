import asyncio
from os import sync

from ariadne import ObjectType

from graphql_api.dataloader.commit import CommitLoader
from graphql_api.dataloader.commit_comparison import CommitComparisonLoader
from graphql_api.dataloader.owner import OwnerLoader
from graphql_api.helpers.connection import queryset_to_connection
from graphql_api.types.enums import OrderingDirection
from graphql_api.types.enums.enums import PullRequestState

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


@pull_bindable.field("compareWithBase")
async def resolve_compare_with_base(pull, info, **kwargs):
    head_commit = None
    compared_commit = None
    comparison = None
    if pull.head is not None and pull.compared_to is not None:
        commit_loader = CommitLoader.loader(info, pull.repository_id)
        head_commit, compared_commit, comparison = await asyncio.gather(
            commit_loader.load(pull.head),
            commit_loader.load(pull.compared_to),
            CommitComparisonLoader.loader(info).load((pull.compared_to, pull.head)),
        )

    command = info.context["executor"].get_command("compare")
    return await command.compare_pull_request(
        pull,
        head_commit=head_commit,
        compared_commit=compared_commit,
        comparison=comparison,
    )


@pull_bindable.field("commits")
async def resolve_commits(pull, info, **kwargs):
    command = info.context["executor"].get_command("commit")
    queryset = await command.fetch_commits_by_pullid(pull)

    return await queryset_to_connection(
        queryset,
        ordering="updatestamp",
        ordering_direction=OrderingDirection.ASC,
        **kwargs,
    )
