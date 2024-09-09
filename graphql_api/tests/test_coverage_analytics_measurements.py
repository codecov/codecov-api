import datetime
from unittest.mock import patch

from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from freezegun import freeze_time

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import (
    CommitFactory,
    RepositoryFactory,
)
from timeseries.models import Interval

from .helper import GraphQLTestHelper

query_coverage_analytics_with_interval = """
query CoverageAnalytics($owner:String!, $repo: String!, $interval: MeasurementInterval!) {
    owner(username:$owner) {
      repository(name: $repo) {
        __typename
        ... on Repository {
          name
          coverageAnalytics {
            %s
          }
        }
        ... on ResolverError {
          message
        }
      }
    }
}
"""

default_coverage_analytics_measurements_fields = """
    measurements(interval: $interval) {
        timestamp
        avg
        min
        max
    }
"""


class TestFetchCoverageAnalyticsWithInterval(GraphQLTestHelper, TransactionTestCase):
    databases = {'default', 'timeseries'}

    def fetch_coverage_analytics(
            self, repo_name, fields=None, interval=None
    ):
        query = query_coverage_analytics_with_interval % (fields or default_coverage_analytics_measurements_fields)
        variables = {"owner": "codecov-user", "repo": repo_name, "interval": interval}

        return self.gql_request(query=query, owner=self.owner, variables=variables)

    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")
        self.yaml = {"test": "test"}

    @freeze_time("2022-01-02")
    def test_coverage_analytics_with_interval(self):
        """Test with interval argument to fetch coverage data in a specific time range"""
        # Create repo, commit, and coverage data within different intervals
        repo = RepositoryFactory(
            author=self.owner,
            active=True,
            private=True,
            name="test",
            yaml=self.yaml,
            language="erlang",
            languages=[],
        )
        one_day_ago = timezone.make_aware(datetime.datetime(2022, 1, 1, 0, 0))
        CommitFactory(repository=repo, totals={"c": 65, "h": 20, "m": 5, "n": 25}, timestamp=one_day_ago)

        two_days_ago = timezone.make_aware(datetime.datetime(2022, 1, 2, 0, 0))
        CommitFactory(repository=repo, totals={"c": 75, "h": 30, "m": 10, "n": 40}, timestamp=two_days_ago)

        # Save repository
        repo.updatestamp = timezone.now()
        repo.save()
        self.assertTrue(
            repo.pk, "Repository should be saved and have a primary key."
        )

        # Fetch the coverage analytics data with interval
        interval = "INTERVAL_1_DAY"
        coverage_analytics_data = self.fetch_coverage_analytics(repo.name, default_coverage_analytics_measurements_fields, interval=interval)

        # Define the expected response based on the interval
        expected_response = {
            "__typename": "Repository",
            "name": repo.name,
            "coverageAnalytics": {
                "measurements":  [
                    {'avg': 65.0, 'max': 65.0, 'min': 65.0, 'timestamp': '2022-01-01T00:00:00+00:00'},
                    {'avg': 75.0, 'max': 75.0, 'min': 75.0, 'timestamp': '2022-01-02T00:00:00+00:00'}
                ]
            },
        }
        assert coverage_analytics_data["owner"]["repository"] == expected_response


@patch("timeseries.helpers.repository_coverage_measurements_with_fallback")
class TestMeasurement(TransactionTestCase, GraphQLTestHelper):
    def _request(self, variables=None):
        query = f"""
            query Measurements($branch: String) {{
                owner(username: "{self.org.username}") {{
                    repository(name: "{self.repo.name}") {{
                        ... on Repository {{
                            coverageAnalytics {{
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
            }}
        """
        data = self.gql_request(query, owner=self.owner, variables=variables)
        return data["owner"]["repository"]["coverageAnalytics"]["measurements"]

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
            {"timestamp_bin": datetime.datetime(2022, 1, 1), "min": 1, "max": 2, "avg": 1.5},
            {"timestamp_bin": datetime.datetime(2022, 1, 2), "min": 3, "max": 4, "avg": 3.5},
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
            start_date=datetime.datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime.datetime(2022, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
            branch=None,
        )


    @override_settings(TIMESERIES_ENABLED=False)
    def test_measurements_timeseries_not_enabled(
        self, repository_coverage_measurements_with_fallback
    ):
        repository_coverage_measurements_with_fallback.return_value = [
            {"timestamp_bin": datetime.datetime(2022, 1, 1), "min": 1, "max": 2, "avg": 1.5},
            {"timestamp_bin": datetime.datetime(2022, 1, 2), "min": 3, "max": 4, "avg": 3.5},
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
            start_date=datetime.datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime.datetime(2022, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
            branch=None,
        )

    @override_settings(TIMESERIES_ENABLED=True)
    def test_measurements_branch(self, repository_coverage_measurements_with_fallback):
        repository_coverage_measurements_with_fallback.return_value = []
        self._request(variables={"branch": "foo"})

        repository_coverage_measurements_with_fallback.assert_called_once_with(
            self.repo,
            Interval.INTERVAL_1_DAY,
            start_date=datetime.datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime.datetime(2022, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
            branch="foo",
        )
