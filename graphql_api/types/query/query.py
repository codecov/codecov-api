from ariadne import ObjectType
from django.conf import settings

from graphql_api.actions.owner import get_owner
from graphql_api.helpers.ariadne import ariadne_load_local_graphql
from graphql_api.types.enums.enums import LoginProvider

query = ariadne_load_local_graphql(__file__, "query.graphql")
query_bindable = ObjectType("Query")


@query_bindable.field("me")
def resolve_me(_, info):
    user = info.context["request"].user
    if not user.is_authenticated:
        return None
    return user


@query_bindable.field("owner")
def resolve_owner(_, info, username):
    service = info.context["service"]
    return get_owner(service, username)


@query_bindable.field("config")
def resolve_config(_, info):
    # we have to return something here just to allow access to the child resolvers
    return object()
