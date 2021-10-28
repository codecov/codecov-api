from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .file import file_bindable

commit_file = ariadne_load_local_graphql(__file__, "file.graphql")
