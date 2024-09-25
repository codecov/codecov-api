from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .coverage_analytics import (
    coverage_analytics_bindable,
    coverage_analytics_result_bindable,
)

coverage_analytics = ariadne_load_local_graphql(__file__, "coverage_analytics.graphql")

__all__ = [
    "coverage_analytics_bindable",
    "coverage_analytics_result_bindable",
]
