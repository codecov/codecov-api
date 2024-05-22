from datetime import datetime, timezone
from unittest.mock import patch

from django.test import TransactionTestCase, override_settings

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from timeseries.models import Interval

from .helper import GraphQLTestHelper


@patch("timeseries.helpers.repository_coverage_measurements_with_fallback")
class TestMeasurement(TransactionTestCase, GraphQLTestHelper):
    def _request(self, variables=None):
        query = f"""
            query Measurements($branch: String) {{
                owner(username: "{self.org.username}") {{
                    repository(name: "{self.repo.name}") {{
                        ... on Repository {{
                            measurements(
                                interval: INTERVAL_1_DAY
                                after: "2022-01-01"
                                before: "2022-01-03"
                                branch: $branch
                            ) {{
                                timestamp
                                avg
                                min
                                max
                            }}
                        }}
                    }}
                }}
            }}
        """
        data = self.gql_request(query, owner=self.owner, variables=variables)
        return data["owner"]["repository"]["measurements"]

    def setUp(self):
        self.org = OwnerFactory(username="test-org")
        self.repo = RepositoryFactory(
            name="test-repo",
            author=self.org,
            private=True,
        )
        self.owner = OwnerFactory(permission=[self.repo.pk])

    @override_settings(TIMESERIES_ENABLED=True)
    def test_measurements_timeseries_enabled(
        self, repository_coverage_measurements_with_fallback
    ):
        repository_coverage_measurements_with_fallback.return_value = [
            {"timestamp_bin": datetime(2022, 1, 1), "min": 1, "max": 2, "avg": 1.5},
            {"timestamp_bin": datetime(2022, 1, 2), "min": 3, "max": 4, "avg": 3.5},
        ]

        assert self._request() == [
            {"timestamp": "2022-01-01T00:00:00", "min": 1.0, "max": 2.0, "avg": 1.5},
            {"timestamp": "2022-01-02T00:00:00", "min": 3.0, "max": 4.0, "avg": 3.5},
            {
                "timestamp": "2022-01-03T00:00:00+00:00",
                "min": None,
                "max": None,
                "avg": None,
            },
        ]

        repository_coverage_measurements_with_fallback.assert_called_once_with(
            self.repo,
            Interval.INTERVAL_1_DAY,
            start_date=datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2022, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
            branch=None,
        )

    @override_settings(TIMESERIES_ENABLED=False)
    def test_measurements_timeseries_not_enabled(
        self, repository_coverage_measurements_with_fallback
    ):
        repository_coverage_measurements_with_fallback.return_value = [
            {"timestamp_bin": datetime(2022, 1, 1), "min": 1, "max": 2, "avg": 1.5},
            {"timestamp_bin": datetime(2022, 1, 2), "min": 3, "max": 4, "avg": 3.5},
        ]

        assert self._request() == [
            {"timestamp": "2022-01-01T00:00:00", "min": 1.0, "max": 2.0, "avg": 1.5},
            {"timestamp": "2022-01-02T00:00:00", "min": 3.0, "max": 4.0, "avg": 3.5},
            {
                "timestamp": "2022-01-03T00:00:00+00:00",
                "min": None,
                "max": None,
                "avg": None,
            },
        ]

        repository_coverage_measurements_with_fallback.assert_called_once_with(
            self.repo,
            Interval.INTERVAL_1_DAY,
            start_date=datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2022, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
            branch=None,
        )

    @override_settings(TIMESERIES_ENABLED=True)
    def test_measurements_branch(self, repository_coverage_measurements_with_fallback):
        repository_coverage_measurements_with_fallback.return_value = []
        self._request(variables={"branch": "foo"})

        repository_coverage_measurements_with_fallback.assert_called_once_with(
            self.repo,
            Interval.INTERVAL_1_DAY,
            start_date=datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2022, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
            branch="foo",
        )
