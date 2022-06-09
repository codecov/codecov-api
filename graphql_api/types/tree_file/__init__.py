from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .tree_file import tree_file_bindable

tree_file = ariadne_load_local_graphql(__file__, "tree_file.graphql")
