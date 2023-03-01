from ariadne import UnionType, convert_kwargs_to_snake_case

from codecov.db import sync_to_async
from core.commands.flag import FlagCommands
from graphql_api.helpers.mutation import (
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
@convert_kwargs_to_snake_case
@sync_to_async
def resolve_delete_flag(_, info, input):
    command: FlagCommands = info.context["executor"].get_command("flag")
    command.delete_flag(
        owner_username=input["owner_username"],
        repo_name=input["repo_name"],
        flag_name=input["flag_name"],
    )


error_delete_flag = UnionType("DeleteFlagError")
error_delete_flag.type_resolver(resolve_union_error_type)
