from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .test_results_aggregates import test_results_aggregates_bindable

test_results_aggregates = ariadne_load_local_graphql(
    __file__, "test_results_aggregates.graphql"
)

__all__ = ["test_results_aggregates_bindable"]
