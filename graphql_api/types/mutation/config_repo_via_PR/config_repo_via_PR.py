from ariadne import UnionType, convert_kwargs_to_snake_case

from graphql_api.helpers.mutation import (
    require_authenticated,
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
@require_authenticated
@convert_kwargs_to_snake_case
async def resolve_config_repository_via_PR(_, info, input):
    command = info.context["executor"].get_command("repository")
    # FIXME
    await command.regenerate_repository_token(
        repo_name=input.get("repo_name"),
        owner_username=input.get("owner"),
        token_type=input.get("token_type"),
    )

    return {"success": int(True)}


error_configure_repo_via_PR = UnionType("ConfigRepositoryViaPRError")
error_configure_repo_via_PR.type_resolver(resolve_union_error_type)
