from ariadne import ObjectType
from asgiref.sync import sync_to_async

from graphql_api.dataloader.owner import load_owner_by_id


commit_bindable = ObjectType("Commit")

commit_bindable.set_alias("createdAt", "timestamp")


@commit_bindable.field("author")
def resolve_author(commit, info):
    if commit.author_id:
        return load_owner_by_id(info, commit.author_id)


@commit_bindable.field("parent")
@sync_to_async
def resolve_parent(commit, info):
    return commit.parent_commit
