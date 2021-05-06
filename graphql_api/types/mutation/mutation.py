from ariadne import MutationType

from .create_api_token import resolve_create_api_token
from .sync_with_git_provider import resolve_sync_with_git_provider
from .delete_session import resolve_delete_session

mutation_bindable = MutationType()

# Here, bind the resolvers from each subfolder to the Mutation type
mutation_bindable.field("createApiToken")(resolve_create_api_token)
mutation_bindable.field("syncWithGitProvider")(resolve_sync_with_git_provider)
mutation_bindable.field("deleteSession")(resolve_delete_session)
