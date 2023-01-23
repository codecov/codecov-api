import logging

from django.conf import settings

log = logging.getLogger(__name__)


class DatabaseRouter:
    """
    A router to control all database operations on models across multiple databases.
    https://docs.djangoproject.com/en/4.0/topics/db/multi-db/#automatic-database-routing
    """

    def db_for_read(self, model, **hints):
        if model._meta.app_label == "timeseries":
            if settings.TIMESERIES_DATABASE_READ_REPLICA_ENABLED:
                return "timeseries_read"
            else:
                return "timeseries"
        else:
            if settings.DATABASE_READ_REPLICA_ENABLED:
                return "default_read"
            else:
                return "default"

    def db_for_write(self, model, **hints):
        if model._meta.app_label == "timeseries":
            return "timeseries"
        else:
            return "default"

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == "timeseries" and not settings.TIMESERIES_ENABLED:
            log.warning("Skipping timeseries migration")
            return False

        if db == "default_read":
            log.warning("Skipping migration of read-only database")
            return False

        if app_label == "timeseries":
            return db == "timeseries"
        else:
            return db == "default"
