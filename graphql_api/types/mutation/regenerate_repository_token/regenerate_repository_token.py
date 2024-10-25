from ariadne import UnionType

from graphql_api.helpers.mutation import (
    require_authenticated,
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
@require_authenticated
async def resolve_regenerate_repository_token(_, info, input):
    command = info.context["executor"].get_command("repository")

    token = await command.regenerate_repository_token(
        repo_name=input.get("repo_name"),
        owner_username=input.get("owner"),
        token_type=input.get("token_type"),
    )

    return {"token": token}


error_regenerate_repository_token = UnionType("RegenerateRepositoryTokenError")
error_regenerate_repository_token.type_resolver(resolve_union_error_type)
