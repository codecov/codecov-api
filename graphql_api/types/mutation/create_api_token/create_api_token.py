from graphql_api.actions.owner import create_api_token


async def resolve_create_api_token(_, info, input):
    current_user = info.context["request"].user
    if not current_user.is_authenticated:
        return {"error": "unauthenticated"}
    session = await create_api_token(current_user, input.get("name"))
    return {
        "session": session,
        "full_token": session.token    
    }
