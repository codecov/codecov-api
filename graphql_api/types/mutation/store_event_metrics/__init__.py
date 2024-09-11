from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .store_event_metrics import error_store_event_metrics, resolve_store_event_metrics

gql_store_event_metrics = ariadne_load_local_graphql(
    __file__, "store_event_metrics.graphql"
)


__all__ = ["error_store_event_metrics", "resolve_store_event_metrics"]
