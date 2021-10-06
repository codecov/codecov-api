from os import sync
from ariadne import ObjectType
from graphql_api.dataloader.owner import load_owner_by_id
from asgiref.sync import sync_to_async

pull_bindable = ObjectType("Pull")

pull_bindable.set_alias("pullId", "pullid")

@pull_bindable.field("author")
def resolve_author(pull, info):
    return load_owner_by_id(info, pull.author_id)

@pull_bindable.field("head")
@sync_to_async
def resolve_head(pull, info):
  from core.models import Commit
  return Commit.objects.get(commitid=pull.head, repository_id=pull.repository_id)

@pull_bindable.field("base")
@sync_to_async
def resolve_base(pull, info):
  from core.models import Commit
  return Commit.objects.get(commitid=pull.base, repository_id=pull.repository_id)