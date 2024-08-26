from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .update_repository import error_update_repository, resolve_update_repository

gql_update_repository = ariadne_load_local_graphql(
    __file__, "update_repository.graphql"
)


__all__ = ["error_update_repository", "resolve_update_repository"]
