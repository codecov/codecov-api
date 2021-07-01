from ariadne import UnionType

from graphql_api.helpers.mutation import (
    wrap_error_handling_mutation,
    resolve_union_error_type,
)
from graphql_api.actions.sync import trigger_sync


@wrap_error_handling_mutation
async def resolve_sync_with_git_provider(_, info):
    current_user = info.context["request"].user
    action_result = await trigger_sync(current_user)
    return {"me": current_user}


error_sync_with_git_provider = UnionType("SyncWithGitProviderError")
error_sync_with_git_provider.type_resolver(resolve_union_error_type)
