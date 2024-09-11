from ariadne import UnionType

from codecov_auth.commands.owner import OwnerCommands
from graphql_api.helpers.mutation import (
    require_authenticated,
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
@require_authenticated
async def resolve_store_event_metrics(_, info, input) -> None:
    command: OwnerCommands = info.context["executor"].get_command("owner")
    await command.store_codecov_metric(
        input.get("org_username"), input.get("event_name"), input.get("json_payload")
    )
    return None


error_store_event_metrics = UnionType("StoreEventMetricsError")
error_store_event_metrics.type_resolver(resolve_union_error_type)
