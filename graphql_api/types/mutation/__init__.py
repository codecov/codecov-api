from graphql_api.helpers.ariadne import ariadne_load_local_graphql

from .activate_flags_measurements import gql_activate_flags_measurements
from .create_api_token import gql_create_api_token
from .create_user_token import gql_create_user_token
from .delete_session import gql_delete_session
from .mutation import mutation_resolvers
from .onboard_user import gql_onboard_user
from .regenerate_org_upload_token import gql_regenerate_org_upload_token
from .regenerate_profiling_token import gql_regenerate_profling_token
from .revoke_user_token import gql_revoke_user_token
from .set_yaml_on_owner import gql_set_yaml_on_owner
from .sync_with_git_provider import gql_sync_with_git_provider
from .update_default_organization import gql_update_default_organization
from .update_profile import gql_update_profile

mutation = ariadne_load_local_graphql(__file__, "mutation.graphql")
mutation = mutation + gql_create_api_token
mutation = mutation + gql_sync_with_git_provider
mutation = mutation + gql_delete_session
mutation = mutation + gql_set_yaml_on_owner
mutation = mutation + gql_update_profile
mutation = mutation + gql_update_default_organization
mutation = mutation + gql_onboard_user
mutation = mutation + gql_regenerate_profling_token
mutation = mutation + gql_activate_flags_measurements
mutation = mutation + gql_regenerate_org_upload_token
mutation = mutation + gql_create_user_token
mutation = mutation + gql_revoke_user_token
