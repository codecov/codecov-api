from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .user_token import user_token_bindable

user_token = ariadne_load_local_graphql(__file__, "user_token.graphql")
