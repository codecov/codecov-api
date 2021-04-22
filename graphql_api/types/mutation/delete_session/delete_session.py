from graphql_api.actions.owner import delete_session


async def resolve_delete_session(_, info, input):
    current_user = info.context["request"].user
    if not current_user.is_authenticated:
        return {"error": "unauthenticated"}
    await delete_session(current_user, input.get("sessionid"))
    return None
