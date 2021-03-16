from ariadne import ObjectType, load_schema_from_path

from graphql_api.helpers import ariadne_load_local_graphql

me = ariadne_load_local_graphql(__file__, "me.graphql")
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
