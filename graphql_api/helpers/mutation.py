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
        except Unauthenticated as e:
            return {"error": "unauthenticated"}
        except Unauthorized as e:
            return {"error": "unauthorized"}
        except ValidationError as e:
            return {"error": str(e)}
        except NotFound as e:
            return {"error": "not found"}

    return resolver_with_error_handling


def new_wrap_error_handling_mutation(resolver):
    async def resolver_with_error_handling(*args, **kwargs):
        try:
            return await resolver(*args, **kwargs)
        except Exception as e:
            print("--------------")
            print(type(e))
            print(issubclass(type(e), BaseException))
            print("--------------")
            if issubclass(type(e), BaseException):
                print("so it wont raise")
                return {"error": e}
            raise e

    return resolver_with_error_handling
