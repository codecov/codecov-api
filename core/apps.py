from django.apps import AppConfig
from shared.helpers.cache import RedisBackend

from services.redis_configuration import get_redis_connection
from utils.cache import cache
from utils.config import RUN_ENV


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        if RUN_ENV not in ["DEV", "TESTING"]:
            cache_backend = RedisBackend(get_redis_connection())
            cache.configure(cache_backend)
