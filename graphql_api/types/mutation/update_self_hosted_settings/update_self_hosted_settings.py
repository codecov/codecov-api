from ariadne import UnionType

from codecov_auth.commands.owner import OwnerCommands
from graphql_api.helpers.mutation import (
    require_authenticated,
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
@require_authenticated
async def resolve_update_self_hosted_settings(_, info, input):
    command: OwnerCommands = info.context["executor"].get_command("owner")
    return await command.update_self_hosted_settings(input)


error_update_self_hosted_settings = UnionType("UpdateSelfHostedSettingsError")
error_update_self_hosted_settings.type_resolver(resolve_union_error_type)
