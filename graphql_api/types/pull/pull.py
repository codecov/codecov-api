from os import sync
from ariadne import ObjectType
from graphql_api.dataloader.owner import load_owner_by_id
from graphql_api.dataloader.commit import load_commit_by_id
from graphql_api.types.enums.enums import PullRequestState

pull_bindable = ObjectType("Pull")

pull_bindable.set_alias("pullId", "pullid")

@pull_bindable.field("state")
def resolve_state(pull, info):
  return PullRequestState(pull.state)

@pull_bindable.field("author")
def resolve_author(pull, info):
  return load_owner_by_id(info, pull.author_id)

@pull_bindable.field("head")
def resolve_head(pull, info):
  return load_commit_by_id(info, pull.head, pull.repository_id)

@pull_bindable.field("base")
def resolve_base(pull, info):
  if pull.base == None:
    return None
  return load_commit_by_id(info, pull.base, pull.repository_id)