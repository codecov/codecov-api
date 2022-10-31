from ariadne import UnionType

from graphql_api.helpers.mutation import (
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
async def resolve_revoke_user_token(_, info, input):
    command = info.context["executor"].get_command("owner")
    await command.revoke_user_token(input.get("tokenid"))
    return None


error_revoke_user_token = UnionType("RevokeUserTokenError")
error_revoke_user_token.type_resolver(resolve_union_error_type)
