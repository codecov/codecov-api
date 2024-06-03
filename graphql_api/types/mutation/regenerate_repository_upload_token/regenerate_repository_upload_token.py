from ariadne import UnionType, convert_kwargs_to_snake_case

from core.commands.repository.repository import RepositoryCommands
from graphql_api.helpers.mutation import (
    require_authenticated,
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
@require_authenticated
async def resolve_regenerate_repository_upload_token(_, info, input):
    command: RepositoryCommands = info.context["executor"].get_command("repository")
    token = await command.regenerate_repository_upload_token(
        repo_name=input.get("repoName"),
        owner_username=input.get("owner"),
    )

    return {"token": token}


error_regenerate_repository_upload_token = UnionType(
    "RegenerateRepositoryUploadTokenError"
)
error_regenerate_repository_upload_token.type_resolver(resolve_union_error_type)
