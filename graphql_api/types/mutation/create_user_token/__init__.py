from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .create_user_token import error_create_user_token, resolve_create_user_token

gql_create_user_token = ariadne_load_local_graphql(
    __file__, "create_user_token.graphql"
)
