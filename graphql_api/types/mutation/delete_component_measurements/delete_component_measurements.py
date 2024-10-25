from ariadne import UnionType

from codecov.db import sync_to_async
from core.commands.component import ComponentCommands
from graphql_api.helpers.mutation import (
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
@sync_to_async
def resolve_delete_component_measurements(_, info, input):
    command: ComponentCommands = info.context["executor"].get_command("component")
    command.delete_component_measurements(
        owner_username=input["owner_username"],
        repo_name=input["repo_name"],
        component_id=input["component_id"],
    )


error_delete_component_measurements = UnionType("DeleteComponentMeasurementsError")
error_delete_component_measurements.type_resolver(resolve_union_error_type)
