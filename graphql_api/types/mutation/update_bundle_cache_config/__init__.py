from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .update_bundle_cache_config import (
    error_update_bundle_cache_config,
    resolve_update_bundle_cache_config,
)

gql_update_bundle_cache_config = ariadne_load_local_graphql(
    __file__, "update_bundle_cache_config.graphql"
)

__all__ = [
    "error_update_bundle_cache_config",
    "resolve_update_bundle_cache_config",
]
