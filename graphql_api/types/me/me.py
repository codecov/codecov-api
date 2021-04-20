from ariadne import ObjectType

from graphql_api.actions.repository import search_repos
from graphql_api.actions.owner import search_my_owners, get_owner_sessions
from graphql_api.helpers.ariadne import ariadne_load_local_graphql
from graphql_api.helpers.connection import (
    build_connection_graphql,
    queryset_to_connection,
)

me = ariadne_load_local_graphql(__file__, "me.graphql")
me = me + build_connection_graphql("ViewableRepositoryConnection", "Repository")
me = me + build_connection_graphql("MyOrganizationConnection", "Owner")
me = me + build_connection_graphql("SessionConnection", "Session")
me_bindable = ObjectType("Me")


@me_bindable.field("user")
def resolve_user(user, _):
    return user


@me_bindable.field("owner")
def resolve_owner(user, _):
    """
    Current user is also an owner in which we can fetch repositories
    """
    return user


@me_bindable.field("viewableRepositories")
def resolve_viewable_repositories(current_user, _, filters=None, **kwargs):
    queryset = search_repos(current_user, filters)
    ordering = ("-repoid",)
    return queryset_to_connection(queryset, ordering, **kwargs)


@me_bindable.field("myOrganizations")
def resolve_my_organizations(current_user, _, filters=None, **kwargs):
    queryset = search_my_owners(current_user, filters)
    ordering = ("-ownerid",)
    return queryset_to_connection(queryset, ordering, **kwargs)


@me_bindable.field("sessions")
def resolve_sessions(current_user, _, **kwargs):
    queryset = get_owner_sessions(current_user)
    ordering = ("-sessionid",)
    return queryset_to_connection(queryset, ordering, **kwargs)
