from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .repository_config import indication_range_bindable, repository_config_bindable

repository_config = ariadne_load_local_graphql(__file__, "repository_config.graphql")
