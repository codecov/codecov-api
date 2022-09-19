from unittest.mock import patch

import pytest
from django.conf import settings
from django.db import connections
from django.test import TransactionTestCase


@pytest.mark.skipif(
    not settings.TIMESERIES_ENABLED, reason="requires timeseries data storage"
)
class DatabaseTests(TransactionTestCase):
    databases = {"timeseries"}

    @patch("django.db.backends.postgresql.base.DatabaseWrapper.is_usable")
    def test_db_reconnect(self, is_usable):
        timeseries_database_engine = settings.DATABASES["timeseries"]["ENGINE"]
        settings.DATABASES["timeseries"]["ENGINE"] = "codecov.db"

        is_usable.return_value = True

        with connections["timeseries"].cursor() as cursor:
            cursor.execute("SELECT 1")

        is_usable.return_value = False

        # it should reconnect and not raise an error
        with connections["timeseries"].cursor() as cursor:
            cursor.execute("SELECT 1")

        settings.DATABASES["timeseries"]["ENGINE"] = timeseries_database_engine
