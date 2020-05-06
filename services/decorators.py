from shared.torngit.exceptions import TorngitClientError
from rest_framework.exceptions import APIException


def torngit_safe(method):
    def exec_method(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except TorngitClientError as e:
            exception = APIException(detail=e.message)
            exception.status_code = e.code
            raise exception
    # This is needed to decorate custom DRF viewset actions
    exec_method.__name__ = method.__name__
    return exec_method
