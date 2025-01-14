from typing import Any, Dict

from ariadne import UnionType
from graphql import GraphQLResolveInfo

from graphql_api.helpers.mutation import (
    require_authenticated,
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
@require_authenticated
async def resolve_save_okta_config(
    _: Any, info: GraphQLResolveInfo, input: Dict[str, Any]
) -> None:
    command = info.context["executor"].get_command("owner")
    return await command.save_okta_config(input)


error_save_okta_config = UnionType("SaveOktaConfigError")
error_save_okta_config.type_resolver(resolve_union_error_type)
