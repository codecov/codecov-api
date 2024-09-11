from ariadne import UnionType

from codecov_auth.commands.owner import OwnerCommands
from graphql_api.helpers.mutation import (
    require_authenticated,
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
@require_authenticated
async def resolve_start_trial(_, info, input) -> None:
    command: OwnerCommands = info.context["executor"].get_command("owner")
    await command.start_trial(input.get("org_username"))
    return None


error_start_trial = UnionType("StartTrialError")
error_start_trial.type_resolver(resolve_union_error_type)
