from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .impacted_file import impacted_file_bindable

impacted_file = ariadne_load_local_graphql(__file__, "impacted_file.graphql")
