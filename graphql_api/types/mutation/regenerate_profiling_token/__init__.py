from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .regenerate_profiling_token import (
    error_generate_profiling_token,
    resolve_regenerate_profling_token,
)

gql_regenerate_profling_token = ariadne_load_local_graphql(
    __file__, "regenerate_profiling_token.graphql"
)
