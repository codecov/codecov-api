import logging

from django.apps import AppConfig
from shared.helpers.cache import RedisBackend

from services.redis_configuration import get_redis_connection
from utils.cache import cache
from utils.config import RUN_ENV

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        import core.signals  # noqa: F401

        if RUN_ENV not in ["DEV", "TESTING"]:
            cache_backend = RedisBackend(get_redis_connection())
            cache.configure(cache_backend)
