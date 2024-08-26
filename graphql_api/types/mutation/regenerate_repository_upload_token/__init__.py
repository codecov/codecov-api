from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .regenerate_repository_upload_token import (
    error_regenerate_repository_upload_token,
    resolve_regenerate_repository_upload_token,
)

gql_regenerate_repository_upload_token = ariadne_load_local_graphql(
    __file__, "regenerate_repository_upload_token.graphql"
)


__all__ = [
    "error_regenerate_repository_upload_token",
    "resolve_regenerate_repository_upload_token",
]
