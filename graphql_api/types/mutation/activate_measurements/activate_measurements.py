from ariadne import UnionType

from core.commands.repository import RepositoryCommands
from graphql_api.helpers.mutation import (
    require_authenticated,
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
@require_authenticated
async def resolve_activate_measurements(_, info, input):
    command: RepositoryCommands = info.context["executor"].get_command("repository")
    await command.activate_measurements(
        owner_name=input.get("owner"),
        repo_name=input.get("repo_name"),
        measurement_type=input.get("measurement_type"),
    )
    return None


error_activate_measurements = UnionType("ActivateMeasurementsError")
error_activate_measurements.type_resolver(resolve_union_error_type)
