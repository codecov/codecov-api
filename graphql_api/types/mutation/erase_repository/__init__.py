from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .erase_repository import error_erase_repository, resolve_erase_repository

gql_erase_repository = ariadne_load_local_graphql(__file__, "erase_repository.graphql")


__all__ = ["error_erase_repository", "resolve_erase_repository"]
