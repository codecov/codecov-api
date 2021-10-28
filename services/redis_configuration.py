from redis import Redis

from utils.config import get_config


def get_redis_url():
    url = get_config("services", "redis_url")
    if url is not None:
        return url
    hostname = "redis"
    port = 6379
    return f"redis://redis:@{hostname}:{port}"


def get_redis_connection() -> Redis:
    url = get_redis_url()
    return _get_redis_instance_from_url(url)


def _get_redis_instance_from_url(url):
    return Redis.from_url(url)
