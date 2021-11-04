from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .delete_session import error_delete_session, resolve_delete_session

gql_delete_session = ariadne_load_local_graphql(__file__, "delete_session.graphql")
