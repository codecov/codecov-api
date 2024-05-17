from ariadne import UnionType, convert_kwargs_to_snake_case
from graphql_api.helpers.mutation import (
    require_authenticated,
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
@require_authenticated
async def resolve_erase_repository(_, info, input) -> None:
    command = info.context["executor"].get_command("repository")
    current_owner = info.context["request"].current_owner
    repo_name = input.get("repoName")
    await command.erase_repository(repo_name=repo_name, owner=current_owner)
    return None


error_erase_repository = UnionType("EraseRepositoryError")
error_erase_repository.type_resolver(resolve_union_error_type)
