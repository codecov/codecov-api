from graphql_api.commands.exceptions import (
    BaseException,
    Unauthenticated,
    ValidationError,
    Unauthorized,
    NotFound,
)


def wrap_error_handling_mutation(resolver):
    async def resolver_with_error_handling(*args, **kwargs):
        try:
            return await resolver(*args, **kwargs)
        except Exception as e:
            if issubclass(type(e), BaseException):
                return {"error": e}
            raise e

    return resolver_with_error_handling
