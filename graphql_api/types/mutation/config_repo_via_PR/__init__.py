from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .config_repo_via_PR import (
    error_configure_repo_via_PR,
    resolve_config_repository_via_PR,
)

gql_config_repo_via_pr = ariadne_load_local_graphql(
    __file__, "config_repo_via_PR.graphql"
)
