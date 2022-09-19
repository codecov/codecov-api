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
        is_usable.return_value = False

        with connections["timeseries"].cursor() as cursor:
            cursor.execute("SELECT 1")
