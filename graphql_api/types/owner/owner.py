from ariadne import ObjectType


from graphql_api.helpers.ariadne import ariadne_load_local_graphql
from graphql_api.helpers.connection import (
    build_connection_graphql,
    queryset_to_connection,
)
from graphql_api.actions.repository import list_repository_for_owner

owner = ariadne_load_local_graphql(__file__, "owner.graphql")
owner = owner + build_connection_graphql("RepositoryConnection", "Repository")
owner_bindable = ObjectType("Owner")


@owner_bindable.field("repositories")
def resolve_repositories(owner, info, **kwargs):
    current_user = info.context["request"].user
    queryset = list_repository_for_owner(current_user, owner)
    ordering = ("-repoid",)
    return queryset_to_connection(queryset, ordering, **kwargs)
