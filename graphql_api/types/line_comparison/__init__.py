from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .line_comparison import line_comparison_bindable

line_comparison = ariadne_load_local_graphql(__file__, "line_comparison.graphql")
