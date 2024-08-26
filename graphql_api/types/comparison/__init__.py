from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .comparison import comparison_bindable, comparison_result_bindable

comparison = ariadne_load_local_graphql(__file__, "comparison.graphql")


__all__ = ["comparison_bindable", "comparison_result_bindable"]
