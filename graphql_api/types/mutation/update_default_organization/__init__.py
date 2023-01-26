from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .update_default_organization import (
    error_update_default_organization,
    resolve_update_default_organization,
)

gql_update_default_organization = ariadne_load_local_graphql(
    __file__, "update_default_organization.graphql"
)
