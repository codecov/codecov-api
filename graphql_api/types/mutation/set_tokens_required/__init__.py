from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .set_tokens_required import (
    error_set_tokens_required,
    resolve_set_tokens_required,
)

gql_set_tokens_required = ariadne_load_local_graphql(
    __file__, "set_tokens_required.graphql"
)

__all__ = ["error_set_tokens_required", "resolve_set_tokens_required"]
