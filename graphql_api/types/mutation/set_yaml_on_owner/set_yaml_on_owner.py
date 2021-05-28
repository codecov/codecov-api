from graphql_api.helpers.mutation import wrap_error_handling_mutation


@wrap_error_handling_mutation
async def resolve_set_yaml_on_owner(_, info, input):
    return {"error": "not yet implemented"}
