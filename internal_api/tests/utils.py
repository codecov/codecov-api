import asyncio
from mock import Mock

class TestUtils(object):
    def get_mock_coro(return_value):
        @asyncio.coroutine
        def mock_coro(*args, **kwargs):
            return return_value

        return Mock(wraps=mock_coro)
