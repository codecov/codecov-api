from ariadne import UnionType, convert_kwargs_to_snake_case

from codecov.db import sync_to_async
from graphql_api.helpers.mutation import (
    require_authenticated,
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
@require_authenticated
@convert_kwargs_to_snake_case
async def resolve_save_okta_config(_, info, input):
    command = info.context["executor"].get_command("owner")
    return await command.save_okta_config(input)

error_save_okta_config = UnionType("SaveOktaConfigError")
error_save_okta_config.type_resolver(resolve_union_error_type)
