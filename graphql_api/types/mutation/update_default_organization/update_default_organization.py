from ariadne import UnionType

from codecov_auth.commands.owner import OwnerCommands
from graphql_api.helpers.mutation import (
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
async def resolve_update_default_organization(_, info, input):
    command: OwnerCommands = info.context["executor"].get_command("owner")
    return await command.update_default_organization(
        default_org_username=input.get("username")
    )


error_update_default_organization = UnionType("UpdateDefaultOrganizationError")
error_update_default_organization.type_resolver(resolve_union_error_type)
