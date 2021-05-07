from graphql_api.helpers.mutation import wrap_error_handling_mutation


@wrap_error_handling_mutation
async def resolve_delete_session(_, info, input):
    command = info.context["executor"].get_command("owner")
    print(input.get("sessionid"))
    print(input.get("sessionid"))
    print(input.get("sessionid"))
    print(input.get("sessionid"))
    await command.delete_session(input.get("sessionid"))
    return None
