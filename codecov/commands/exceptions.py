from graphql import GraphQLError


class BaseException(Exception):
    pass


class Unauthenticated(BaseException):
    message = "You are not authenticated"


class ValidationError(BaseException):
    @property
    def message(self):
        return str(self)


class Unauthorized(BaseException):
    message = "You are not authorized"


class NotFound(BaseException):
    message = "Cant find the requested resource"


class MissingService(BaseException):
    message = "Missing required service"


class UnauthorizedGuestAccess(GraphQLError):
    def __init__(self):
        super().__init__("Unauthorized", extensions={"status": 403})
