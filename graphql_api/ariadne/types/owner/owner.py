from ariadne import ObjectType

from graphql_api.helpers import ariadne_load_local_graphql
from graphql_api.actions.repository import list_repository_for_owner

owner = ariadne_load_local_graphql(__file__, "owner.graphql")
owner_bindable = ObjectType("Owner")

@owner_bindable.field("repositories")
def resolve_repositories(owner, info):
    actor = info.context['request'].user
    return list_repository_for_owner(actor, owner)
