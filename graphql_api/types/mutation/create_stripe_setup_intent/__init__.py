from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .create_stripe_setup_intent import (
    error_create_stripe_setup_intent,
    resolve_create_stripe_setup_intent,
)

gql_create_stripe_setup_intent = ariadne_load_local_graphql(
    __file__, "create_stripe_setup_intent.graphql"
)

__all__ = ["error_create_stripe_setup_intent", "resolve_create_stripe_setup_intent"]
