from typing import Any

from ariadne import UnionType
from graphql import GraphQLResolveInfo

from graphql_api.helpers.mutation import (
    require_authenticated,
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
@require_authenticated
async def resolve_erase_repository(
    _: Any, info: GraphQLResolveInfo, input: dict[str, Any]
) -> None:
    command = info.context["executor"].get_command("repository")
    current_owner = info.context["request"].current_owner

    owner_username = input.get("owner") or current_owner.username
    repo_name = input.get("repo_name")

    await command.erase_repository(owner_username, repo_name)
    return None


error_erase_repository = UnionType("EraseRepositoryError")
error_erase_repository.type_resolver(resolve_union_error_type)
