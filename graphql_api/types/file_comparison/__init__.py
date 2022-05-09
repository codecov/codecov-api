from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .file_comparison import file_comparison_bindable

file_comparison = ariadne_load_local_graphql(__file__, "file_comparison.graphql")
