from ariadne import UnionType
from graphql_api.helpers.mutation import (
    wrap_error_handling_mutation,
    resolve_union_error_type,
)


@wrap_error_handling_mutation
async def resolve_regenerate_profling_token(_, info, input):
    command = info.context["executor"].get_command("repository")
    profilingToken = await command.regenerate_profiling_token(repoName=input.get("repoName"))
    return {"profiling_token": profilingToken}

error_generate_profiling_token = UnionType("RegenerateProfilingTokenError")
error_generate_profiling_token.type_resolver(resolve_union_error_type)
