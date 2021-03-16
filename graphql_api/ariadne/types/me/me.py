from ariadne import ObjectType, load_schema_from_path

from graphql_api.actions.repository import search_repos
from graphql_api.actions.owner import search_my_owners
from graphql_api.helpers.ariadne import ariadne_load_local_graphql
from graphql_api.helpers.connection import build_connection_graphql, queryset_to_connection

me = ariadne_load_local_graphql(__file__, "me.graphql")
me = me + build_connection_graphql("ViewableRepositoryConnection", "Repository")
me = me + build_connection_graphql("MyOrganizationConnection", "Owner")
me_bindable = ObjectType("Me")


@me_bindable.field("user")
def resolve_user(user, info):
    return user


@me_bindable.field("owner")
def resolve_owner(user, info):
    """
    Current user is also an owner in which we can fetch repositories
    """
    return user


@me_bindable.field("viewableRepositories")
def resolve_viewable_repositories(user, info, filters = None, **kwargs):
    current_user = info.context['request'].user
    queryset = search_repos(current_user, filters)
    ordering=('-repoid',)
    return queryset_to_connection(queryset, ordering, **kwargs)


@me_bindable.field("myOrganizations")
def resolve_my_organizations(user, info, filters = None, **kwargs):
    current_user = info.context['request'].user
    queryset = search_my_owners(current_user, filters)
    ordering=('-ownerid',)
    return queryset_to_connection(queryset, ordering, **kwargs)
