from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .pull import pull_bindable

pull = ariadne_load_local_graphql(__file__, "pull.graphql")
