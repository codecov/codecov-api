from graphql_api.helpers.mutation import wrap_error_handling_mutation


@wrap_error_handling_mutation
async def resolve_set_yaml_on_owner(_, info, input):
    command = info.context["executor"].get_command("owner")
    username_input = input.get("username")
    yaml_input = input.get("yaml")
    owner = await command.set_yaml_on_owner(username_input, yaml_input)
    return {"owner": owner}
