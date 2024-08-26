from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .update_self_hosted_settings import (
    error_update_self_hosted_settings,
    resolve_update_self_hosted_settings,
)

gql_update_self_hosted_settings = ariadne_load_local_graphql(
    __file__, "update_self_hosted_settings.graphql"
)

__all__ = [
    "gql_update_self_hosted_settings",
    "error_update_self_hosted_settings",
    "resolve_update_self_hosted_settings",
]
