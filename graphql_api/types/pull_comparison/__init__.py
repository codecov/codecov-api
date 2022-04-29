from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .pull_comparison import pull_comparison_bindable

pull_comparison = ariadne_load_local_graphql(__file__, "pull_comparison.graphql")
