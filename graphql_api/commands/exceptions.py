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
