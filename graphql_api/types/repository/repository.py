from ariadne import ObjectType

from graphql_api.dataloader.owner import load_owner_by_id

repository_bindable = ObjectType("Repository")

@repository_bindable.field("author")
def resolve_author(repository, info):
    return load_owner_by_id(info, 2)
