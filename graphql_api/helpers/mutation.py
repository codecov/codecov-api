from graphql_api.commands import exceptions


class WrappedException:
    """
    Our own class to wrap a Python exception as the core GraphQL library would
    reraise an exception if a resolver returns an error (https://github.com/graphql-python/graphql-core/blob/c602d00b8a8f78bc349a911e0c26d73e1a9bbbac/src/graphql/execution/execute.py#L663-L666)
    so we need to wrap it with a class that is not an Exception; so we can pass
    it as a value to be returned by the mutation
    """

    exception = None

    def __init__(self, exception):
        self.exception = exception

    def get_graphql_type(self):
        """
        Map an exception from "graphql_api.commands.exceptions" to a GraphQL type
        """
        error_to_graphql_type = {
            exceptions.Unauthenticated: "UnauthenticatedError",
            exceptions.Unauthorized: "UnauthorizedError",
            exceptions.NotFound: "NotFoundError",
            exceptions.ValidationError: "ValidationError",
        }
        type_exception = type(self.exception)
        return error_to_graphql_type.get(type_exception, None)

    def __getattr__(self, attr):
        """
        Proxy all the attribute to the exception itself
        """
        return getattr(self.exception, attr)


def wrap_error_handling_mutation(resolver):
    async def resolver_with_error_handling(*args, **kwargs):
        try:
            return await resolver(*args, **kwargs)
        except Exception as e:
            if issubclass(type(e), exceptions.BaseException):
                # Wrap a pure Python exception with our Wrapper to pass as a value
                return {"error": e.old_message, "new_error": WrappedException(e)}
            raise e

    return resolver_with_error_handling


def resolve_union_error_type(error, *_):
    return error.get_graphql_type()
