from graphql_api.actions.sync import trigger_sync


async def resolve_sync_with_git_provider(_, info):
    current_user = info.context["request"].user
    action_result = await trigger_sync(current_user)
    error = action_result.get("error")
    return {"me": current_user if not error else None, "error": error}
