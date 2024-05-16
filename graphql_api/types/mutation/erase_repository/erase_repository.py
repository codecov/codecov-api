from ariadne import UnionType, convert_kwargs_to_snake_case

from graphql_api.helpers.mutation import (
    resolve_union_error_type,
    wrap_error_handling_mutation,
    require_authenticated,
)


@wrap_error_handling_mutation
@convert_kwargs_to_snake_case
@require_authenticated
async def resolve_erase_repository(_, info, input):
    command = info.context["executor"].get_command("repository")
    current_owner = info.context["request"].current_owner
    repo_name = (input.get("repo_name"),)

    await command.erase_repository(repo=repo_name, owner=current_owner)


error_erase_repository = UnionType("EraseRepositoryError")
error_erase_repository.type_resolver(resolve_union_error_type)
