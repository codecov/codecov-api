import stripe
from rest_framework.exceptions import APIException
from shared.torngit.exceptions import TorngitClientError


def torngit_safe(method):
    """
    Translatess torngit exceptions into DRF APIExceptions.
    For use in DRF views.
    """

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


def stripe_safe(method):
    """
    Translates stripe-api errors into DRF APIExceptions.
    """

    def exec_method(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except stripe.error.StripeError as e:
            exception = APIException(detail=e.user_message)
            exception.status_code = e.http_status
            raise exception

    exec_method.__name__ = method.__name__
    return exec_method
