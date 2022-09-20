from unittest.mock import patch

import pytest
from django.conf import settings
from django.test import TestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from reports.tests.factories import RepositoryFlagFactory
from timeseries.models import MeasurementName
from timeseries.tests.factories import DatasetFactory, MeasurementFactory


@pytest.mark.skipif(
    not settings.TIMESERIES_ENABLED, reason="requires timeseries data storage"
)
@patch("api.shared.repo.repository_accessors.RepoAccessors.get_repo_permissions")
class CoverageViewSetTestCase(TestCase):
    databases = {"default", "timeseries"}

    def setUp(self):
        self.org = OwnerFactory(username="codecov", service="github")
        self.repo = RepositoryFactory(author=self.org, name="test-repo", active=True)
        self.user = OwnerFactory(
            username="codecov-user",
            service="github",
            organizations=[self.org.ownerid],
            permission=[self.repo.repoid],
        )

    @patch("timeseries.models.Dataset.is_backfilled")
    def test_repo_coverage(self, get_repo_permissions, is_backfilled):
        get_repo_permissions.return_value = (True, True)
        is_backfilled.return_value = True

        DatasetFactory(
            repository_id=self.repo.pk,
            name=MeasurementName.COVERAGE.value,
        )

        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            timestamp="2022-08-18T00:12:00",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="master",
            value=80.0,
        )
        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            timestamp="2022-08-18T00:13:00",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="master",
            value=90.0,
        )
        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            timestamp="2022-08-19T00:01:00",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="master",
            value=100.0,
        )
        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            timestamp="2022-08-18T00:12:00",
            owner_id=self.org.pk,
            repo_id=9999,
            branch="master",
            value=10.0,
        )

        self.client.force_login(user=self.user)
        response = self.client.get(
            f"/api/v2/github/codecov/repos/{self.repo.name}/coverage?interval=1d&start_date=2022-08-18&end_date=2022-08-19"
        )
        assert response.status_code == 200
        assert response.json() == {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {
                    "timestamp": "2022-08-18T00:00:00Z",
                    "min": 80.0,
                    "max": 90.0,
                    "avg": 85.0,
                },
                {
                    "timestamp": "2022-08-19T00:00:00Z",
                    "min": 100.0,
                    "max": 100.0,
                    "avg": 100.0,
                },
            ],
            "total_pages": 1,
        }

    @patch("timeseries.models.Dataset.is_backfilled")
    def test_repo_coverage_branch(self, get_repo_permissions, is_backfilled):
        get_repo_permissions.return_value = (True, True)
        is_backfilled.return_value = True

        DatasetFactory(
            repository_id=self.repo.pk,
            name=MeasurementName.COVERAGE.value,
        )

        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            timestamp="2022-08-18T00:12:00",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="other",
            value=80.0,
        )
        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            timestamp="2022-08-18T00:13:00",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="master",
            value=90.0,
        )
        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            timestamp="2022-08-19T00:01:00",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch="other",
            value=100.0,
        )
        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            timestamp="2022-08-18T00:12:00",
            owner_id=self.org.pk,
            repo_id=9999,
            branch="other",
            value=10.0,
        )

        self.client.force_login(user=self.user)
        response = self.client.get(
            f"/api/v2/github/codecov/repos/{self.repo.name}/coverage?interval=1d&start_date=2022-08-18&end_date=2022-08-19&branch=other"
        )
        assert response.status_code == 200
        assert response.json() == {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {
                    "timestamp": "2022-08-18T00:00:00Z",
                    "min": 80.0,
                    "max": 80.0,
                    "avg": 80.0,
                },
                {
                    "timestamp": "2022-08-19T00:00:00Z",
                    "min": 100.0,
                    "max": 100.0,
                    "avg": 100.0,
                },
            ],
            "total_pages": 1,
        }

    def test_repo_coverage_no_interval(self, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)

        self.client.force_login(user=self.user)
        response = self.client.get(
            f"/api/v2/github/codecov/repos/{self.repo.name}/coverage"
        )
        assert response.status_code == 422

    def test_repo_coverage_invalid_interval(self, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)

        self.client.force_login(user=self.user)
        response = self.client.get(
            f"/api/v2/github/codecov/repos/{self.repo.name}/coverage?interval=wrong"
        )
        assert response.status_code == 422

    def test_flag_coverage(self, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)

        flag1 = RepositoryFlagFactory(
            repository=self.repo,
            flag_name="flag1",
        )
        flag2 = RepositoryFlagFactory(
            repository=self.repo,
            flag_name="flag1",
        )

        MeasurementFactory(
            name=MeasurementName.FLAG_COVERAGE.value,
            timestamp="2022-08-18T00:12:00",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            flag_id=flag1.pk,
            branch="master",
            value=80.0,
        )
        MeasurementFactory(
            name=MeasurementName.FLAG_COVERAGE.value,
            timestamp="2022-08-18T00:13:00",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            flag_id=flag1.pk,
            branch="master",
            value=90.0,
        )
        MeasurementFactory(
            name=MeasurementName.FLAG_COVERAGE.value,
            timestamp="2022-08-19T00:01:00",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            flag_id=flag1.pk,
            branch="master",
            value=100.0,
        )
        MeasurementFactory(
            name=MeasurementName.FLAG_COVERAGE.value,
            timestamp="2022-08-18T00:12:00",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            flag_id=flag2.pk,
            branch="master",
            value=10.0,
        )

        self.client.force_login(user=self.user)
        response = self.client.get(
            f"/api/v2/github/codecov/repos/{self.repo.name}/flags/{flag1.flag_name}/coverage?interval=1d&start_date=2022-08-18&end_date=2022-08-19"
        )
        assert response.status_code == 200
        assert response.json() == {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {
                    "timestamp": "2022-08-18T00:00:00Z",
                    "min": 80.0,
                    "max": 90.0,
                    "avg": 85.0,
                },
                {
                    "timestamp": "2022-08-19T00:00:00Z",
                    "min": 100.0,
                    "max": 100.0,
                    "avg": 100.0,
                },
            ],
            "total_pages": 1,
        }

    def test_flag_coverage_missing_flag(self, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)

        self.client.force_login(user=self.user)
        response = self.client.get(
            f"/api/v2/github/codecov/repos/{self.repo.name}/flags/wrong-flag/coverage?interval=1d&start_date=2022-08-18&end_date=2022-08-19"
        )
        assert response.status_code == 200
        assert response.json() == {
            "count": 0,
            "next": None,
            "previous": None,
            "results": [],
            "total_pages": 1,
        }
