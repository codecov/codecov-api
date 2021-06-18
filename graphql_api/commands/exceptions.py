class BaseException:
    pass


class Unauthenticated(BaseException):
    message = "You are not authenticated"


class ValidationError(BaseException):
    pass


class Unauthorized(BaseException):
    message = "You are not authorized"


class NotFound(BaseException):
    message = "Cant find the requested resource"
