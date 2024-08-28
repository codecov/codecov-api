from shared.license import get_current_license

from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .test_results import test_result_bindable

test_results = ariadne_load_local_graphql(__file__, "test_results.graphql")

__all__ = ["get_current_license", "test_result_bindable"]
