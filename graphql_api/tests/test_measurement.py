from datetime import datetime, timezone
from unittest.mock import PropertyMock, patch

import pytest
from django.conf import settings
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from timeseries.tests.factories import MeasurementFactory

from .helper import GraphQLTestHelper

base_query = """{
    me {
        owner {
            measurements(
                name: "testing"
                interval: INTERVAL_1_DAY
                filters: %s
            ) {
                timestamp
                avg
                min
                max
            }
        }
    }
}
"""


@pytest.mark.skipif(
    not settings.TIMESERIES_ENABLED, reason="requires timeseries data storage"
)
class TestMeasurement(TransactionTestCase, GraphQLTestHelper):
    databases = {"default", "timeseries"}

    def _request(self, filters):
        data = self.gql_request(base_query % filters, user=self.user)
        return data["me"]["owner"]["measurements"]

    def setUp(self):
        self.user = OwnerFactory()
        self.repo = RepositoryFactory(
            author=self.user,
            private=True,
        )

    def test_measurements_empty_filter(self):
        res = self._request(
            f"""
            [
                {{
                    after: "2000-01-01T00:00:00"
                    before: "{timezone.now().isoformat()}"
                }}
            ]
            """,
        )
        assert len(res) == 1
        measurements = res[0]
        assert len(measurements) == 0

    def test_measurements_basic(self):
        MeasurementFactory(value=1, owner_id=self.user.pk, repo_id=self.repo.pk)
        MeasurementFactory(value=2, owner_id=self.user.pk, repo_id=self.repo.pk)

        # should not be included in response since the `name` does not match query
        MeasurementFactory(
            value=3, owner_id=self.user.pk, repo_id=self.repo.pk, name="other"
        )
        # should not be included in response since the `owner_id` does not match query
        MeasurementFactory(value=3, owner_id=999, repo_id=self.repo.pk)

        res = self._request(
            f"""
            [
                {{
                    after: "2000-01-01T00:00:00"
                    before: "{timezone.now().isoformat()}"
                }}
            ]
            """,
        )

        assert len(res) == 1
        measurements = res[0]
        assert len(measurements) == 1
        assert measurements[0]["avg"] == 1.5
        assert measurements[0]["min"] == 1
        assert measurements[0]["max"] == 2

    def test_measurements_filter_by_repo(self):
        MeasurementFactory(value=1, repo_id=self.repo.pk, owner_id=self.user.pk)
        MeasurementFactory(value=2, repo_id=999, owner_id=self.user.pk)

        res = self._request(
            f"""
            [
                {{
                    after: "2000-01-01T00:00:00"
                    before: "{timezone.now().isoformat()}"
                    repoId: {self.repo.pk}
                }}
            ]
            """,
        )

        assert len(res) == 1
        # only considers measurements for specified repo
        measurements = res[0]
        assert len(measurements) == 1
        assert measurements[0]["avg"] == 1

    def test_measurements_filter_by_flag(self):
        MeasurementFactory(
            value=1, repo_id=self.repo.pk, owner_id=self.user.pk, flag_id=1
        )
        MeasurementFactory(
            value=2, repo_id=self.repo.pk, owner_id=self.user.pk, flag_id=2
        )

        res = self._request(
            f"""
            [
                {{
                    after: "2000-01-01T00:00:00"
                    before: "{timezone.now().isoformat()}"
                    flagId: 1
                }}
            ]
            """,
        )

        assert len(res) == 1
        # only considers measurements for specified flag
        measurements = res[0]
        assert len(measurements) == 1
        assert measurements[0]["avg"] == 1

    def test_measurements_filter_by_branch(self):
        MeasurementFactory(
            value=1, repo_id=self.repo.pk, owner_id=self.user.pk, branch="foo"
        )
        MeasurementFactory(
            value=2, repo_id=self.repo.pk, owner_id=self.user.pk, branch="bar"
        )

        res = self._request(
            f"""
            [
                {{
                    after: "2000-01-01T00:00:00"
                    before: "{timezone.now().isoformat()}"
                    branch: "foo"
                }}
            ]
            """,
        )

        assert len(res) == 1
        # only considers measurements for specified branch
        measurements = res[0]
        assert len(measurements) == 1
        assert measurements[0]["avg"] == 1

    def test_measurements_compound_filter(self):
        MeasurementFactory(
            value=1, repo_id=self.repo.pk, owner_id=self.user.pk, branch="foo"
        )
        MeasurementFactory(
            value=2, repo_id=self.repo.pk, owner_id=self.user.pk, branch="bar"
        )

        res = self._request(
            f"""
            [
                {{
                    after: "2000-01-01T00:00:00"
                    before: "{timezone.now().isoformat()}"
                    repoId: {self.repo.pk}
                    branch: "foo"
                }}
            ]
            """,
        )

        assert len(res) == 1
        # only considers measurements for specified branch
        measurements = res[0]
        assert len(measurements) == 1
        assert measurements[0]["avg"] == 1

    def test_measurements_multiple_filters(self):
        MeasurementFactory(
            value=1, repo_id=self.repo.pk, owner_id=self.user.pk, branch="foo"
        )
        MeasurementFactory(
            value=2, repo_id=self.repo.pk, owner_id=self.user.pk, branch="bar"
        )

        res = self._request(
            f"""
            [
                {{
                    after: "2000-01-01T00:00:00"
                    before: "{timezone.now().isoformat()}"
                    repoId: {self.repo.pk}
                    branch: "foo"
                }}
                {{
                    after: "2000-01-01T00:00:00"
                    before: "{timezone.now().isoformat()}"
                    repoId: {self.repo.pk}
                    branch: "bar"
                }}
            ]
            """,
        )

        assert len(res) == 2
        # only considers measurements for specified branch
        measurements = res[0]
        assert len(measurements) == 1
        assert measurements[0]["avg"] == 1
        measurements = res[1]
        assert len(measurements) == 1
        assert measurements[0]["avg"] == 2

    def test_measurements_filter_by_after(self):
        MeasurementFactory(
            value=1,
            repo_id=self.repo.pk,
            owner_id=self.user.pk,
            timestamp=datetime(2022, 1, 2, 0, 0, 0),
        )
        MeasurementFactory(
            value=2,
            repo_id=self.repo.pk,
            owner_id=self.user.pk,
            timestamp=datetime(2022, 1, 1, 0, 0, 0),
        )

        res = self._request(
            f"""
            [
                {{
                    after: "2022-01-02"
                    before: "{timezone.now().isoformat()}"
                    repoId: {self.repo.pk}
                }}
            ]
            """,
        )

        assert len(res) == 1
        # only considers measurements after specified datetime
        measurements = res[0]
        assert len(measurements) == 1
        assert measurements[0]["avg"] == 1

    def test_measurements_filter_by_before(self):
        MeasurementFactory(
            value=1,
            repo_id=self.repo.pk,
            owner_id=self.user.pk,
            timestamp=datetime(2022, 1, 1, 0, 0, 0),
        )
        MeasurementFactory(
            value=2,
            repo_id=self.repo.pk,
            owner_id=self.user.pk,
            timestamp=datetime(2022, 1, 2, 0, 0, 0),
        )

        res = self._request(
            f"""
            [
                {{
                    after: "2000-01-01T00:00:00"
                    before: "2022-01-01"
                    repoId: {self.repo.pk}
                }}
            ]
            """,
        )

        assert len(res) == 1
        # only considers measurements before specified datetime
        measurements = res[0]
        assert len(measurements) == 1
        assert measurements[0]["avg"] == 1

    def test_measurements_no_access(self):
        repo = RepositoryFactory(
            private=True,
        )
        MeasurementFactory(value=1, owner_id=repo.author_id, repo_id=repo.pk)

        res = self._request(
            f"""
            [
                {{
                    after: "2000-01-01T00:00:00"
                    before: "{timezone.now().isoformat()}"
                    repoId: {self.repo.pk}
                }}
            ]
            """,
        )

        # current user has no access to above repo so
        # measurements are not included in response
        assert len(res) == 1
        measurements = res[0]
        assert len(measurements) == 0

    @override_settings(TIMESERIES_ENABLED=False)
    def test_measurements_timeseries_not_enabled(self):
        repo = RepositoryFactory(
            private=True,
        )
        MeasurementFactory(value=1, owner_id=repo.author_id, repo_id=repo.pk)

        res = self._request(
            f"""
            [
                {{
                    after: "2000-01-01T00:00:00"
                    before: "{timezone.now().isoformat()}"
                    repoId: {self.repo.pk}
                }}
            ]
            """,
        )

        assert len(res) == 1
        measurements = res[0]
        assert len(measurements) == 0
