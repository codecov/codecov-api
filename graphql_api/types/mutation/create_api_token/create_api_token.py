from ariadne import UnionType
from graphql_api.helpers.mutation import (
    wrap_error_handling_mutation,
    new_wrap_error_handling_mutation,
)


@wrap_error_handling_mutation
async def resolve_create_api_token(_, info, input):
    command = info.context["executor"].get_command("owner")
    session = await command.create_api_token(input.get("name"))
    return {"session": session, "full_token": session.token}


error_create_api_token = UnionType("CreateApiTokenError")

from graphql_api.commands import exceptions

error_to_type = {
    exceptions.Unauthenticated: "UnauthenticatedError",
    exceptions.Unauthorized: "UnauthorizedError",
    exceptions.NotFound: "NotFoundError",
    exceptions.ValidationError: "ValidationError",
}


@error_create_api_token.type_resolver
def resolve_error_type(error, *_):
    type_error = type(error)
    return error_to_type.get(type_error, None)
