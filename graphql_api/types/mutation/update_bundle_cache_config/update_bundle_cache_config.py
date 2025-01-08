from typing import Any, Dict, List

from ariadne import UnionType
from graphql import GraphQLResolveInfo

from core.commands.repository.repository import RepositoryCommands
from graphql_api.helpers.mutation import (
    require_authenticated,
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
@require_authenticated
async def resolve_update_bundle_cache_config(
    _: Any, info: GraphQLResolveInfo, input: Dict[str, Any]
) -> Dict[str, List[Dict[str, str | bool]]]:
    command: RepositoryCommands = info.context["executor"].get_command("repository")

    results = await command.update_bundle_cache_config(
        repo_name=input.get("repo_name", ""),
        owner_username=input.get("owner", ""),
        cache_config=input.get("bundles", []),
    )
    return {"results": results}


error_update_bundle_cache_config = UnionType("UpdateBundleCacheConfigError")
error_update_bundle_cache_config.type_resolver(resolve_union_error_type)
