from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .settings import settings_bindable

settings = ariadne_load_local_graphql(__file__, "settings.graphql")
