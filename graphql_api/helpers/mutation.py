from codecov.commands import exceptions
from codecov_auth.helpers import current_user_part_of_org


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
        Map an exception from "codecov.commands.exceptions" to a GraphQL type
        """
        error_to_graphql_type = {
            exceptions.Unauthenticated: "UnauthenticatedError",
            exceptions.Unauthorized: "UnauthorizedError",
            exceptions.NotFound: "NotFoundError",
            exceptions.ValidationError: "ValidationError",
            exceptions.MissingService: "MissingService",
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
        except exceptions.BaseException as e:
            # Wrap a pure Python exception with our Wrapper to pass as a value
            return {"error": WrappedException(e)}

    return resolver_with_error_handling


def require_authenticated(resolver):
    def authenticated_resolver(instance, info, *args, **kwargs):
        current_user = info.context["request"].user
        if not current_user.is_authenticated:
            raise exceptions.Unauthenticated()

        return resolver(instance, info, *args, **kwargs)

    return authenticated_resolver


def require_part_of_org(resolver):
    def authenticated_resolver(queried_owner, info, *args, **kwargs):
        current_user = info.context["request"].user
        current_owner = info.context["request"].current_owner
        if (
            not current_user
            or not current_user.is_authenticated
            or not current_owner
            or not current_user_part_of_org(current_owner, queried_owner)
        ):
            return None

        return resolver(queried_owner, info, *args, **kwargs)

    return authenticated_resolver


def require_shared_account_or_part_of_org(resolver):
    def authenticated_resolver(queried_owner, info, *args, **kwargs):
        current_user = info.context["request"].user
        if (
            current_user
            and current_user.is_authenticated
            and queried_owner
            and queried_owner.account
            and current_user in queried_owner.account.users.all()
        ):
            return resolver(queried_owner, info, *args, **kwargs)

        return require_part_of_org(resolver)(queried_owner, info, *args, **kwargs)

    return authenticated_resolver


def resolve_union_error_type(error, *_):
    return error.get_graphql_type()
