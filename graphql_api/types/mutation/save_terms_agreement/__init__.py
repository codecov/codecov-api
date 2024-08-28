from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .save_terms_agreement import (
    error_save_terms_agreement,
    resolve_save_terms_agreement,
)

gql_save_terms_agreement = ariadne_load_local_graphql(
    __file__, "save_terms_agreement.graphql"
)

__all__ = ["error_save_terms_agreement", "resolve_save_terms_agreement"]
