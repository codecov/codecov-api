from datetime import datetime, timezone

from django.test import TestCase, TransactionTestCase

from timeseries.models import MeasurementSummary

from .factories import MeasurementFactory


class MeasurementTests(TestCase):
    databases = {"timeseries"}

    def test_measurement_agg_hour(self):
        MeasurementFactory(
            timestamp=datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc), value=1
        )
        MeasurementFactory(
            timestamp=datetime(2022, 1, 1, 0, 1, 0, tzinfo=timezone.utc), value=2
        )
        MeasurementFactory(
            timestamp=datetime(2022, 1, 1, 0, 2, 0, tzinfo=timezone.utc), value=3
        )
        MeasurementFactory(
            timestamp=datetime(2022, 1, 1, 1, 1, 0, tzinfo=timezone.utc), value=4
        )
        MeasurementFactory(
            timestamp=datetime(2022, 1, 1, 1, 2, 0, tzinfo=timezone.utc), value=5
        )

        results = MeasurementSummary.agg_by("hour").all()

        assert len(results) == 2
        assert results[0].value_avg == 2
        assert results[0].value_min == 1
        assert results[0].value_max == 3
        assert results[0].value_count == 3
        assert results[1].value_avg == 4.5
        assert results[1].value_min == 4
        assert results[1].value_max == 5
        assert results[1].value_count == 2

    def test_measurement_agg_day(self):
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

        results = MeasurementSummary.agg_by("day").all()

        assert len(results) == 2
        assert results[0].value_avg == 2
        assert results[0].value_min == 1
        assert results[0].value_max == 3
        assert results[0].value_count == 3
        assert results[1].value_avg == 4.5
        assert results[1].value_min == 4
        assert results[1].value_max == 5
        assert results[1].value_count == 2

    def test_measurement_agg_week(self):
        # Week 1: Monday, Tuesday, Sunday
        MeasurementFactory(timestamp=datetime(2022, 1, 3), value=1)
        MeasurementFactory(timestamp=datetime(2022, 1, 4), value=2)
        MeasurementFactory(timestamp=datetime(2022, 1, 9), value=3)

        # Week 2: Monday, Sunday
        MeasurementFactory(timestamp=datetime(2022, 1, 10), value=4)
        MeasurementFactory(timestamp=datetime(2022, 1, 16), value=5)

        results = MeasurementSummary.agg_by("week").all()

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
