from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .save_sentry_state import error_save_sentry_state, resolve_save_sentry_state

gql_save_sentry_state = ariadne_load_local_graphql(
    __file__, "save_sentry_state.graphql"
)

__all__ = ["error_save_sentry_state", "resolve_save_sentry_state"]
