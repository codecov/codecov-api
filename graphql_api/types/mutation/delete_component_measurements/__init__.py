from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .delete_component_measurements import (
    error_delete_component_measurements,
    resolve_delete_component_measurements,
)

gql_delete_component_measurements = ariadne_load_local_graphql(
    __file__, "delete_component_measurements.graphql"
)


__all__ = [
    "error_delete_component_measurements",
    "resolve_delete_component_measurements",
]
