from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .cancel_trial import error_cancel_trial, resolve_cancel_trial

gql_cancel_trial = ariadne_load_local_graphql(__file__, "cancel_trial.graphql")


__all__ = ["error_cancel_trial", "resolve_cancel_trial"]
