from ariadne import ObjectType

from graphql_api.helpers.ariadne import ariadne_load_local_graphql

user = ariadne_load_local_graphql(__file__, "user.graphql")

user_bindable = ObjectType("User")
