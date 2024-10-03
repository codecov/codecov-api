from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .test_results_headers import test_results_headers_bindable

test_results_headers = ariadne_load_local_graphql(
    __file__, "test_results_headers.graphql"
)

__all__ = ["test_results_headers_bindable"]
