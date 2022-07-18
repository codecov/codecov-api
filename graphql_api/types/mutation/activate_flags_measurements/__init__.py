from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .activate_flags_measurements import (
    error_activate_flags_measurements,
    resolve_activate_flags_measurements,
)

gql_activate_flags_measurements = ariadne_load_local_graphql(
    __file__, "activate_flags_measurements.graphql"
)
