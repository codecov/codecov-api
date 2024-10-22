from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .set_upload_token_required import (
    error_set_upload_token_required,
    resolve_set_upload_token_required,
)

gql_set_upload_token_required = ariadne_load_local_graphql(
    __file__, "set_upload_token_required.graphql"
)

__all__ = ["error_set_upload_token_required", "resolve_set_upload_token_required"]
