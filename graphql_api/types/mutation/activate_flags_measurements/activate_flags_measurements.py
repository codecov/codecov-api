from ariadne import UnionType

from graphql_api.helpers.mutation import (
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
async def resolve_activate_flags_measurements(_, info, input):
    command = info.context["executor"].get_command("repository")
    await command.activate_flags_measurements(
        owner_name=input.get("owner"),
        repo_name=input.get("repoName"),
    )
    return None


error_activate_flags_measurements = UnionType("ActivateFlagsMeasurementsError")
error_activate_flags_measurements.type_resolver(resolve_union_error_type)
