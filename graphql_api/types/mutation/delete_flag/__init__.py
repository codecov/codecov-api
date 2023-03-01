from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .delete_flag import error_delete_flag, resolve_delete_flag

gql_delete_flag = ariadne_load_local_graphql(__file__, "delete_flag.graphql")
