from shared.torngit.exceptions import TorngitClientGeneralError


def to_drf_datetime_str(datetime):
    """
    DRF does custom datetime representation, which makes comparing
    expected timestamps in tests really annoying. This function tries
    to mimic DRF datetime representation using ISO-8601 format, minus
    reading from gobal formatting settings.

    source: https://github.com/encode/django-rest-framework/blob/aed74961ba03e3e6f53c468353f4e255eb788555/rest_framework/fields.py#L1227
    """
    value = datetime.isoformat()
    if value.endswith("+00:00"):
        value = value[:-6] + "Z"
    return value


class GetAdminProviderAdapter:
    """
    Mock adapter providing the `get_is_admin` coroutine, which returns `self.result`.
    """

    def __init__(self, result=False):
        self.result = result
        self.last_call_args = None

    async def get_is_admin(self, user):
        self.last_call_args = user
        return self.result


class GetAdminErrorProviderAdapter:
    """
    Mock adapter that raises a torngit error.
    """

    def __init__(self, code, message):
        self.code = code
        self.message = message

    async def get_is_admin(self, user):
        raise TorngitClientGeneralError(
            self.code, response_data=None, message=self.message
        )
