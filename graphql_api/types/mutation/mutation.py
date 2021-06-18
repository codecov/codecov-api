from ariadne import MutationType

from .create_api_token import resolve_create_api_token, error_create_api_token
from .sync_with_git_provider import resolve_sync_with_git_provider
from .set_yaml_on_owner import resolve_set_yaml_on_owner
from .delete_session import resolve_delete_session

mutation_bindable = MutationType()

# Here, bind the resolvers from each subfolder to the Mutation type
mutation_bindable.field("createApiToken")(resolve_create_api_token)
mutation_bindable.field("setYamlOnOwner")(resolve_set_yaml_on_owner)
mutation_bindable.field("syncWithGitProvider")(resolve_sync_with_git_provider)
mutation_bindable.field("deleteSession")(resolve_delete_session)

mutation_resolvers = [mutation_bindable, error_create_api_token]
