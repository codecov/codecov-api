class BaseException(Exception):
    pass


class Unauthenticated(BaseException):
    message = "You are not authenticated"
    old_message = "unauthenticated"


class ValidationError(BaseException):
    message = "Bad input"
    old_message = "bad data you gave me"


class Unauthorized(BaseException):
    message = "You are not authorized"
    old_message = "unauthorized"


class NotFound(BaseException):
    message = "Cant find the requested resource"
    old_message = "not found"
