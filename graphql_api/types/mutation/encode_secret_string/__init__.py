from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .encode_secret_string import (
    error_encode_secret_string,
    resolve_encode_secret_string,
)

gql_encode_secret_string = ariadne_load_local_graphql(
    __file__, "encode_secret_string.graphql"
)

__all__ = ["error_encode_secret_string", "resolve_encode_secret_string"]
