from ariadne import UnionType, convert_kwargs_to_snake_case

from graphql_api.helpers.mutation import (
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
@convert_kwargs_to_snake_case
async def resolve_onboard_user(_, info, input):
    command = info.context["executor"].get_command("owner")
    input["goals"] = [goal.value for goal in input.get("goals", [])]
    input["type_projects"] = [goal.value for goal in input.get("type_projects", [])]
    return {"me": await command.onboard_user(input)}


error_onboard_user = UnionType("OnboardUserError")
error_onboard_user.type_resolver(resolve_union_error_type)
