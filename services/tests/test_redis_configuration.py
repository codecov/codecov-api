from shared.helpers.redis import get_redis_connection


def test_get_redis_connection(mocker):
    mocker.patch("shared.helpers.redis.get_config", return_value=None)
    mocked = mocker.patch("shared.helpers.redis.Redis.from_url")
    res = get_redis_connection()
    assert res is not None
    mocked.assert_called_with("redis://redis:6379")
