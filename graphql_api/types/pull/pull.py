from os import sync

from ariadne import ObjectType

from graphql_api.dataloader.commit import load_commit_by_id
from graphql_api.dataloader.owner import load_owner_by_id
from graphql_api.types.enums.enums import PullRequestState

pull_bindable = ObjectType("Pull")

pull_bindable.set_alias("pullId", "pullid")


@pull_bindable.field("state")
def resolve_state(pull, info):
    return PullRequestState(pull.state)


@pull_bindable.field("author")
def resolve_author(pull, info):
    if pull.author_id:
        return load_owner_by_id(info, pull.author_id)


@pull_bindable.field("head")
def resolve_head(pull, info):
    if pull.head == None:
        return None
    return load_commit_by_id(info, pull.head, pull.repository_id)


@pull_bindable.field("comparedTo")
def resolve_base(pull, info):
    if pull.compared_to == None:
        return None
    return load_commit_by_id(info, pull.compared_to, pull.repository_id)


@pull_bindable.field("compareWithBase")
def resolve_compare_with_base(pull, info, **kwargs):
    command = info.context["executor"].get_command("compare")
    return command.compare_pull_request(pull)
