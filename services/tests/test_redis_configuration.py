from services.redis_configuration import get_redis_connection


def test_get_redis_connection(mocker):
    mocker.patch("services.redis_configuration.get_config", return_value=None)
    mocked = mocker.patch("services.redis_configuration.Redis.from_url")
    res = get_redis_connection()
    assert res is not None
    mocked.assert_called_with("redis://redis:6379")
