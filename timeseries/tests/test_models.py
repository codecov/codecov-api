from datetime import datetime, timezone

import pytest
from django.conf import settings
from django.test import TransactionTestCase
from freezegun import freeze_time

from timeseries.models import Dataset, Interval, MeasurementName, MeasurementSummary

from .factories import DatasetFactory, MeasurementFactory


@pytest.mark.skipif(
    not settings.TIMESERIES_ENABLED, reason="requires timeseries data storage"
)
class MeasurementTests(TransactionTestCase):
    databases = {"timeseries"}

    def test_measurement_agg_1day(self):
        MeasurementFactory(
            timestamp=datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc), value=1
        )
        MeasurementFactory(
            timestamp=datetime(2022, 1, 1, 1, 0, 0, tzinfo=timezone.utc), value=2
        )
        MeasurementFactory(
            timestamp=datetime(2022, 1, 1, 1, 0, 1, tzinfo=timezone.utc), value=3
        )
        MeasurementFactory(
            timestamp=datetime(2022, 1, 2, 0, 0, 0, tzinfo=timezone.utc), value=4
        )
        MeasurementFactory(
            timestamp=datetime(2022, 1, 2, 0, 1, 0, tzinfo=timezone.utc), value=5
        )

        results = MeasurementSummary.agg_by(Interval.INTERVAL_1_DAY).all()

        assert len(results) == 2
        assert results[0].value_avg == 2
        assert results[0].value_min == 1
        assert results[0].value_max == 3
        assert results[0].value_count == 3
        assert results[1].value_avg == 4.5
        assert results[1].value_min == 4
        assert results[1].value_max == 5
        assert results[1].value_count == 2

    def test_measurement_agg_7day(self):
        # Week 1: Monday, Tuesday, Sunday
        MeasurementFactory(timestamp=datetime(2022, 1, 3), value=1)
        MeasurementFactory(timestamp=datetime(2022, 1, 4), value=2)
        MeasurementFactory(timestamp=datetime(2022, 1, 9), value=3)

        # Week 2: Monday, Sunday
        MeasurementFactory(timestamp=datetime(2022, 1, 10), value=4)
        MeasurementFactory(timestamp=datetime(2022, 1, 16), value=5)

        results = MeasurementSummary.agg_by(Interval.INTERVAL_7_DAY).all()

        assert len(results) == 2
        assert results[0].value_avg == 2
        assert results[0].value_min == 1
        assert results[0].value_max == 3
        assert results[0].value_count == 3
        assert results[1].value_avg == 4.5
        assert results[1].value_min == 4
        assert results[1].value_max == 5
        assert results[1].value_count == 2

    def test_measurement_agg_30day(self):
        # Timescale's origin for time buckets is 2000-01-03
        # 30 day offsets will be aligned on that origin

        MeasurementFactory(timestamp=datetime(2000, 1, 3), value=1)
        MeasurementFactory(timestamp=datetime(2000, 1, 4), value=2)
        MeasurementFactory(timestamp=datetime(2000, 2, 1), value=3)

        MeasurementFactory(timestamp=datetime(2000, 2, 2), value=4)
        MeasurementFactory(timestamp=datetime(2000, 2, 11), value=5)

        results = MeasurementSummary.agg_by(Interval.INTERVAL_30_DAY).all()

        assert len(results) == 2
        assert results[0].value_avg == 2
        assert results[0].value_min == 1
        assert results[0].value_max == 3
        assert results[0].value_count == 3
        assert results[1].value_avg == 4.5
        assert results[1].value_min == 4
        assert results[1].value_max == 5
        assert results[1].value_count == 2

    def test_measurement_agg_invalid(self):
        with self.assertRaises(ValueError):
            MeasurementSummary.agg_by("invalid").all()


@pytest.mark.skipif(
    not settings.TIMESERIES_ENABLED, reason="requires timeseries data storage"
)
class DatasetTests(TransactionTestCase):
    databases = {"timeseries"}

    @freeze_time("2022-01-01T01:00:01+0000")
    def test_is_backfilled_true(self):
        dataset = DatasetFactory()

        Dataset.objects.filter(pk=dataset.pk).update(
            created_at=datetime(2022, 1, 1, 0, 0, 0)
        )

        dataset.refresh_from_db()
        assert dataset.is_backfilled() == True

    @freeze_time("2022-01-01T00:59:59+0000")
    def test_is_backfilled_false(self):
        dataset = DatasetFactory()

        Dataset.objects.filter(pk=dataset.pk).update(
            created_at=datetime(2022, 1, 1, 0, 0, 0)
        )

        dataset.refresh_from_db()
        assert dataset.is_backfilled() == False

    def test_is_backfilled_no_created_at(self):
        dataset = DatasetFactory()

        Dataset.objects.filter(pk=dataset.pk).update(created_at=None)

        dataset.refresh_from_db()
        assert dataset.is_backfilled() == False
