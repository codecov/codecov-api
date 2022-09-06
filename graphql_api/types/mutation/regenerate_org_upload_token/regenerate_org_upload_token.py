from ariadne import UnionType

from graphql_api.helpers.mutation import (
    resolve_union_error_type,
    wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
async def resolve_regenerate_org_upload_token(_, info, input):
    command = info.context["executor"].get_command("owner")
    orgUploadToken = await command.regenerate_org_upload_token(owner=input.get("owner"))
    return {"org_upload_token": orgUploadToken}


error_generate_org_upload_token = UnionType("RegenerateOrgUploadTokenError")
error_generate_org_upload_token.type_resolver(resolve_union_error_type)
