from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .activate_component_measurements import (
    error_activate_component_measurements,
    resolve_activate_component_measurements,
)

gql_activate_component_measurements = ariadne_load_local_graphql(
    __file__, "activate_component_measurements.graphql"
)
