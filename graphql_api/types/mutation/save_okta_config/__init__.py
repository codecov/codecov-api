from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .save_okta_config import error_save_okta_config, resolve_save_okta_config

gql_save_okta_config = ariadne_load_local_graphql(__file__, "save_okta_config.graphql")


__all__ = ["error_save_okta_config", "resolve_save_okta_config"]
