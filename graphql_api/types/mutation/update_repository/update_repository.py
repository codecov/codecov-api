from ariadne import UnionType

from graphql_api.helpers.mutation import (
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
async def resolve_update_repository(_, info, input):
    command = info.context["executor"].get_command("repository")
    owner = info.context["request"].current_owner
    repo_name = input.get("repo_name")
    default_branch = input.get("branch")
    activated = input.get("activated")
    await command.update_repository(
        repo_name,
        owner,
        default_branch,
        activated,
    )


error_update_repository = UnionType("UpdateRepositoryError")
error_update_repository.type_resolver(resolve_union_error_type)
