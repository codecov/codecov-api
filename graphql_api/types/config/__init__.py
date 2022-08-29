from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .config import config_bindable

config = ariadne_load_local_graphql(__file__, "config.graphql")
