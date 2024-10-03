from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .flake_aggregates import flake_aggregates_bindable

flake_aggregates = ariadne_load_local_graphql(__file__, "flake_aggregates.graphql")

__all__ = ["flake_aggregates_bindable"]
