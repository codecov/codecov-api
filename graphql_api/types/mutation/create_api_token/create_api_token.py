from ariadne import UnionType

from graphql_api.helpers.mutation import (
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
async def resolve_create_api_token(_, info, input):
    command = info.context["executor"].get_command("owner")
    session = await command.create_api_token(input.get("name"))
    return {"session": session, "full_token": session.token}


error_create_api_token = UnionType("CreateApiTokenError")
error_create_api_token.type_resolver(resolve_union_error_type)
