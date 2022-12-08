from django.conf import settings
import logging


log = logging.getLogger(__name__)

class DatabaseRouter:
    """
    A router to control all database operations on models across multiple databases.
    https://docs.djangoproject.com/en/4.0/topics/db/multi-db/#automatic-database-routing
    """

    # mapping of app label -> database name
    # (if an entry is missing then the `default` database is assumed)
    databases = {
        "timeseries": "timeseries",
    }

    def db_for_read(self, model, **hints):
        return self.databases.get(model._meta.app_label, "default")

    def db_for_write(self, model, **hints):
        return self.databases.get(model._meta.app_label, "default")

    def allow_relation(self, obj1, obj2, **hints):
        obj1_database = self.databases.get(obj1._meta.app_label, "default")
        obj2_database = self.databases.get(obj2._meta.app_label, "default")
        return obj1_database == obj2_database

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == "timeseries" and not settings.TIMESERIES_ENABLED:
            log.warning("Skipping timeseries migration")
            return False

        return db == self.databases.get(app_label, "default")
