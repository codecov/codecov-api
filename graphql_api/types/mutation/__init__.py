from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .create_api_token import gql_create_api_token
from .delete_session import gql_delete_session
from .mutation import mutation_resolvers
from .onboard_user import gql_onboard_user
from .set_yaml_on_owner import gql_set_yaml_on_owner
from .sync_with_git_provider import gql_sync_with_git_provider
from .update_profile import gql_update_profile

mutation = ariadne_load_local_graphql(__file__, "mutation.graphql")
mutation = mutation + gql_create_api_token
mutation = mutation + gql_sync_with_git_provider
mutation = mutation + gql_delete_session
mutation = mutation + gql_set_yaml_on_owner
mutation = mutation + gql_update_profile
mutation = mutation + gql_onboard_user
