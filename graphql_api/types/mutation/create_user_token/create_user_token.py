from ariadne import UnionType

from graphql_api.helpers.mutation import (
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
async def resolve_create_user_token(_, info, input):
    command = info.context["executor"].get_command("owner")
    user_token = await command.create_user_token(
        name=input.get("name"),
        token_type=input.get("tokenType"),
    )
    return {
        "token": user_token,
        "full_token": user_token.token,
    }


error_create_user_token = UnionType("CreateUserTokenError")
error_create_user_token.type_resolver(resolve_union_error_type)
