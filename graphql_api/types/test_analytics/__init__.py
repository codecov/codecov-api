from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .test_analytics import (
    test_analytics_bindable,
)

test_analytics = ariadne_load_local_graphql(__file__, "test_analytics.graphql")

__all__ = [
    "test_analytics_bindable",
]
