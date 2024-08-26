from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .start_trial import error_start_trial, resolve_start_trial

gql_start_trial = ariadne_load_local_graphql(__file__, "start_trial.graphql")


__all__ = ["error_start_trial", "resolve_start_trial"]
