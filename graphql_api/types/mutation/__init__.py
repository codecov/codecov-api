from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .create_api_token import gql_create_api_token
from .delete_session import gql_delete_session
from .mutation import mutation_bindable

mutation = ariadne_load_local_graphql(__file__, "mutation.graphql")
mutation = mutation + gql_create_api_token
mutation = mutation + gql_delete_session
