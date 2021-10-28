from ariadne import UnionType

from graphql_api.helpers.mutation import (
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
async def resolve_update_profile(_, info, input):
    command = info.context["executor"].get_command("owner")
    me = await command.update_profile(email=input.get("email"), name=input.get("name"))
    return {"me": me}


error_update_profile = UnionType("UpdateProfileError")
error_update_profile.type_resolver(resolve_union_error_type)
