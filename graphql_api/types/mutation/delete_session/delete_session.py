from ariadne import UnionType

from graphql_api.helpers.mutation import (
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
async def resolve_delete_session(_, info, input):
    command = info.context["executor"].get_command("owner")
    await command.delete_session(input.get("sessionid"))
    return None


error_delete_session = UnionType("DeleteSessionError")
error_delete_session.type_resolver(resolve_union_error_type)
