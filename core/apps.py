import logging

from django.apps import AppConfig
from django.core.management import call_command
from shared.helpers.cache import RedisBackend

from services.redis_configuration import get_redis_connection
from utils.cache import cache
from utils.config import RUN_ENV

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        import core.signals  # noqa: F401

        if RUN_ENV == "DEV":
            try:
                # Call your management command here
                call_command(
                    "insert_data_to_db_from_csv",
                    "core/management/commands/codecovTiers-Jan25.csv",
                    "--model",
                    "tiers",
                )
                call_command(
                    "insert_data_to_db_from_csv",
                    "core/management/commands/codecovPlans-Jan25.csv",
                    "--model",
                    "plans",
                )
            except Exception as e:
                logger.error(f"Failed to run startup command: {e}")

        if RUN_ENV not in ["DEV", "TESTING"]:
            cache_backend = RedisBackend(get_redis_connection())
            cache.configure(cache_backend)
