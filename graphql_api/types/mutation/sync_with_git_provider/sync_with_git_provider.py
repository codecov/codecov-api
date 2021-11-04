from ariadne import UnionType

from graphql_api.helpers.mutation import (
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
async def resolve_sync_with_git_provider(_, info):
    command = info.context["executor"].get_command("owner")
    command.trigger_sync()
    return {"me": info.context["request"].user}


error_sync_with_git_provider = UnionType("SyncWithGitProviderError")
error_sync_with_git_provider.type_resolver(resolve_union_error_type)
