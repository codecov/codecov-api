from ariadne import ObjectType
from asgiref.sync import sync_to_async

from graphql_api.helpers.ariadne import ariadne_load_local_graphql

query = ariadne_load_local_graphql(__file__, "query.graphql")
query_bindable = ObjectType("Query")


@query_bindable.field("me")
@sync_to_async
def resolve_me(_, info):
    user = info.context["request"].user
    if not user.is_authenticated:
        return None
    return user
