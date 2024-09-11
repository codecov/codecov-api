from ariadne import UnionType

from graphql_api.helpers.mutation import (
    require_authenticated,
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
@require_authenticated
async def resolve_encode_secret_string(_, info, input) -> None:
    command = info.context["executor"].get_command("repository")
    repo_name = input.get("repo_name")
    value = input.get("value")
    current_owner = info.context["request"].current_owner
    value = command.encode_secret_string(
        repo_name=repo_name, owner=current_owner, value=value
    )
    return {"value": value}


error_encode_secret_string = UnionType("EraseRepositoryError")
error_encode_secret_string.type_resolver(resolve_union_error_type)
