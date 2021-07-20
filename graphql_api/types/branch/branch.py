from ariadne import ObjectType

from graphql_api.dataloader.owner import load_owner_by_id


branch_bindable = ObjectType("Branch")


@branch_bindable.field("head")
def resolve_head_commit(repository, info):
    return load_owner_by_id(info, repository.author_id)
