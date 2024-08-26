from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .activate_measurements import (
    error_activate_measurements,
    resolve_activate_measurements,
)

gql_activate_measurements = ariadne_load_local_graphql(
    __file__, "activate_measurements.graphql"
)


__all__ = ["error_activate_measurements", "resolve_activate_measurements"]
