from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .okta_config import okta_config_bindable

okta_config = ariadne_load_local_graphql(__file__, "okta_config.graphql")


__all__ = ["okta_config_bindable"]
