from shared.license import get_current_license

from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .flake_aggregates import flake_aggregates_bindable

flake_aggregates = ariadne_load_local_graphql(__file__, "flake_aggregates.graphql")

__all__ = ["get_current_license", "flake_aggregates_bindable"]
