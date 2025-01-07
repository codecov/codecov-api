from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .update_bundle_caching import (
    error_update_bundle_caching,
    resolve_update_bundle_caching,
)

gql_update_bundle_caching = ariadne_load_local_graphql(
    __file__, "update_bundle_caching.graphql"
)

__all__ = [
    "error_update_bundle_caching",
    "resolve_update_bundle_caching",
]
