from ariadne import UnionType, convert_kwargs_to_snake_case

from graphql_api.helpers.mutation import (
    require_authenticated,
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
@require_authenticated
@convert_kwargs_to_snake_case
async def resolve_regenerate_repository_upload_token(_, info, input):
    command = info.context["executor"].get_command("repository")
    owner = info.context["request"].current_owner

    token = await command.regenerate_repository_upload_token(
        repo_name=input.get("repo_name"), owner=owner
    )

    return token

error_regenerate_repository_upload_token = UnionType(
    "RegenerateRepositoryUploadTokenError"
)
error_regenerate_repository_upload_token.type_resolver(resolve_union_error_type)