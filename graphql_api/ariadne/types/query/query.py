from ariadne import ObjectType

from graphql_api.helpers import ariadne_load_local_graphql

query = ariadne_load_local_graphql(__file__, "query.graphql")
query_bindable = ObjectType("Query")

@query_bindable.field("me")
def resolve_me(_, info):
    user = info.context['request'].user
    if not user.is_authenticated:
        return None
    return user
