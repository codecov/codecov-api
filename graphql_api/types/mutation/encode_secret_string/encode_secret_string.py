from ariadne import UnionType

from core.commands.repository import RepositoryCommands
from graphql_api.helpers.mutation import (require_authenticated,
                                          resolve_union_error_type,
                                          wrap_error_handling_mutation)


@wrap_error_handling_mutation
@require_authenticated
async def resolve_encode_secret_string(_, info, input):
    command: RepositoryCommands = info.context["executor"].get_command("repository")
    current_owner = info.context["request"].current_owner

    return await command.encode_secret_string(current_owner, input)


error_encode_secret_string = UnionType("EncodeSecretStringError")
error_encode_secret_string.type_resolver(resolve_union_error_type)
