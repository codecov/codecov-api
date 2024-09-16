from ariadne import UnionType

from codecov_auth.commands.owner import OwnerCommands
from graphql_api.helpers.mutation import (
    require_authenticated,
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
@require_authenticated
async def resolve_set_tokens_required(_, info, input):
    command: OwnerCommands = info.context["executor"].get_command("owner")
    return await command.set_tokens_required(input)


error_set_tokens_required = UnionType("SetTokensRequiredError")
error_set_tokens_required.type_resolver(resolve_union_error_type)
