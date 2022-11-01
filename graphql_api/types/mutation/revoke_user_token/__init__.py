from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .revoke_user_token import error_revoke_user_token, resolve_revoke_user_token

gql_revoke_user_token = ariadne_load_local_graphql(
    __file__, "revoke_user_token.graphql"
)
