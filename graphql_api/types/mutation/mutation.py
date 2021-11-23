from ariadne import MutationType

from .create_api_token import error_create_api_token, resolve_create_api_token
from .delete_session import error_delete_session, resolve_delete_session
from .onboard_user import error_onboard_user, resolve_onboard_user
from .set_yaml_on_owner import error_set_yaml_error, resolve_set_yaml_on_owner
from .sync_with_git_provider import (
    error_sync_with_git_provider,
    resolve_sync_with_git_provider,
)
from .update_profile import error_update_profile, resolve_update_profile

mutation_bindable = MutationType()

# Here, bind the resolvers from each subfolder to the Mutation type
mutation_bindable.field("createApiToken")(resolve_create_api_token)
mutation_bindable.field("setYamlOnOwner")(resolve_set_yaml_on_owner)
mutation_bindable.field("syncWithGitProvider")(resolve_sync_with_git_provider)
mutation_bindable.field("deleteSession")(resolve_delete_session)
mutation_bindable.field("updateProfile")(resolve_update_profile)
mutation_bindable.field("onboardUser")(resolve_onboard_user)

mutation_resolvers = [
    mutation_bindable,
    error_create_api_token,
    error_set_yaml_error,
    error_sync_with_git_provider,
    error_delete_session,
    error_update_profile,
    error_onboard_user,
]
