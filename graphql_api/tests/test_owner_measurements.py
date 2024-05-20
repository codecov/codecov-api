from datetime import datetime, timezone
from unittest.mock import patch

from django.test import TransactionTestCase, override_settings

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from timeseries.models import Interval

from .helper import GraphQLTestHelper


@patch("timeseries.helpers.owner_coverage_measurements_with_fallback")
class TestOwnerMeasurements(TransactionTestCase, GraphQLTestHelper):
    def _request(self, variables=None):
        query = f"""
            query Measurements($repos: [String!]) {{
                owner(username: "{self.org.username}") {{
                    measurements(
                        interval: INTERVAL_1_DAY
                        after: "2022-01-01"
                        before: "2022-01-03"
                        repos: $repos
                    ) {{
                        timestamp
                        avg
                        min
                        max
                    }}
                }}
            }}
        """
        data = self.gql_request(query, owner=self.owner, variables=variables)
        return data["owner"]["measurements"]

    def setUp(self):
        self.org = OwnerFactory(username="test-org")
        self.repo1 = RepositoryFactory(
            name="test-repo1",
            author=self.org,
            private=True,
        )
        self.repo2 = RepositoryFactory(
            name="test-repo2",
            author=self.org,
            private=False,
        )
        self.owner = OwnerFactory(permission=[self.repo1.pk, self.repo2.pk])

    @override_settings(TIMESERIES_ENABLED=True)
    def test_measurements_timeseries_enabled(
        self, owner_coverage_measurements_with_fallback
    ):
        owner_coverage_measurements_with_fallback.return_value = [
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

        owner_coverage_measurements_with_fallback.assert_called_once_with(
            self.org,
            [self.repo2.pk, self.repo1.pk],
            Interval.INTERVAL_1_DAY,
            start_date=datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2022, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
        )

    @override_settings(TIMESERIES_ENABLED=True)
    def test_measurements_timeseries_enabled_repoids(
        self, owner_coverage_measurements_with_fallback
    ):
        owner_coverage_measurements_with_fallback.return_value = [
            {"timestamp_bin": datetime(2022, 1, 1), "min": 1, "max": 2, "avg": 1.5},
            {"timestamp_bin": datetime(2022, 1, 2), "min": 3, "max": 4, "avg": 3.5},
        ]

        assert self._request(variables={"repos": ["test-repo1"]}) == [
            {"timestamp": "2022-01-01T00:00:00", "min": 1.0, "max": 2.0, "avg": 1.5},
            {"timestamp": "2022-01-02T00:00:00", "min": 3.0, "max": 4.0, "avg": 3.5},
            {
                "timestamp": "2022-01-03T00:00:00+00:00",
                "min": None,
                "max": None,
                "avg": None,
            },
        ]

        owner_coverage_measurements_with_fallback.assert_called_once_with(
            self.org,
            [self.repo1.pk],
            Interval.INTERVAL_1_DAY,
            start_date=datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2022, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
        )

    @override_settings(TIMESERIES_ENABLED=False)
    def test_measurements_timeseries_not_enabled(
        self, owner_coverage_measurements_with_fallback
    ):
        owner_coverage_measurements_with_fallback.return_value = [
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

        owner_coverage_measurements_with_fallback.assert_called_once_with(
            self.org,
            [self.repo2.pk, self.repo1.pk],
            Interval.INTERVAL_1_DAY,
            start_date=datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2022, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
        )

    @override_settings(TIMESERIES_ENABLED=True)
    def test_repository_filtering_by_public_private(
        self, owner_coverage_measurements_with_fallback
    ):
        owner_coverage_measurements_with_fallback.return_value = []
        query = f"""
            query Measurements($isPublic: Boolean) {{
                owner(username: "{self.org.username}") {{
                    measurements(
                        interval: INTERVAL_1_DAY
                        isPublic: $isPublic
                    ) {{
                        timestamp
                    }}
                }}
            }}
        """

        self.gql_request(query, owner=self.owner, variables={"isPublic": False})[
            "owner"
        ]["measurements"]
        params = owner_coverage_measurements_with_fallback.call_args.args
        # Check that the call is using only repo_ids of the private repo
        assert params[1] == [self.repo1.pk]

        self.gql_request(query, owner=self.owner, variables={"isPublic": True})[
            "owner"
        ]["measurements"]
        params = owner_coverage_measurements_with_fallback.call_args.args
        # Check that the call is using only repo_ids of the public repo
        assert params[1] == [self.repo2.pk]

        self.gql_request(query, owner=self.owner, variables={"isPublic": None})[
            "owner"
        ]["measurements"]
        params = owner_coverage_measurements_with_fallback.call_args.args
        # Check that the call is using both private and public repos
        assert set(params[1]) == set([self.repo1.pk, self.repo2.pk])

        query = f"""
            query Measurements {{
                owner(username: "{self.org.username}") {{
                    measurements(
                        interval: INTERVAL_1_DAY
                    ) {{
                        timestamp
                    }}
                }}
            }}
        """
        self.gql_request(query, owner=self.owner)["owner"]["measurements"]
        params = owner_coverage_measurements_with_fallback.call_args.args
        # Check that the call is using both private and public repos
        assert set(params[1]) == set([self.repo1.pk, self.repo2.pk])
