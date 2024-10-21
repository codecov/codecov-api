from datetime import datetime
from unittest.mock import patch

import pytest
from asgiref.sync import async_to_sync
from django.conf import settings
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from freezegun import freeze_time
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    RepositoryFactory,
)

from codecov.commands.exceptions import ValidationError
from timeseries.models import Dataset, MeasurementName

from ..activate_measurements import ActivateMeasurementsInteractor


@pytest.mark.skipif(
    not settings.TIMESERIES_ENABLED, reason="requires timeseries data storage"
)
class ActivateMeasurementsInteractorTest(TransactionTestCase):
    databases = {"default", "timeseries"}

    def setUp(self):
        self.org = OwnerFactory(username="test-org")
        self.repo = RepositoryFactory(author=self.org, name="test-repo", active=True)
        self.user = OwnerFactory(permission=[self.repo.pk])

    @async_to_sync
    def execute(self, owner, repo_name=None, measurement_type=None):
        return ActivateMeasurementsInteractor(owner, "github").execute(
            repo_name=repo_name or "test-repo",
            owner_name="test-org",
            measurement_type=measurement_type or MeasurementName.FLAG_COVERAGE,
        )

    def test_repo_not_found(self):
        with pytest.raises(ValidationError):
            self.execute(owner=self.user, repo_name="wrong")

    @override_settings(TIMESERIES_ENABLED=False)
    def test_timeseries_not_enabled(self):
        with pytest.raises(ValidationError):
            self.execute(owner=self.user)

    @patch("services.task.TaskService.backfill_dataset")
    def test_creates_flag_dataset(self, backfill_dataset):
        assert not Dataset.objects.filter(
            name=MeasurementName.FLAG_COVERAGE.value,
            repository_id=self.repo.pk,
        ).exists()

        self.execute(owner=self.user)

        assert Dataset.objects.filter(
            name=MeasurementName.FLAG_COVERAGE.value,
            repository_id=self.repo.pk,
        ).exists()

    @patch("services.task.TaskService.backfill_dataset")
    def test_creates_component_dataset(self, backfill_dataset):
        assert not Dataset.objects.filter(
            name=MeasurementName.COMPONENT_COVERAGE.value,
            repository_id=self.repo.pk,
        ).exists()

        self.execute(
            owner=self.user,
            repo_name="test-repo",
            measurement_type=MeasurementName.COMPONENT_COVERAGE,
        )

        assert Dataset.objects.filter(
            name=MeasurementName.COMPONENT_COVERAGE.value,
            repository_id=self.repo.pk,
        ).exists()

    @patch("services.task.TaskService.backfill_dataset")
    def test_creates_coverage_dataset(self, backfill_dataset):
        assert not Dataset.objects.filter(
            name=MeasurementName.COVERAGE.value,
            repository_id=self.repo.pk,
        ).exists()

        self.execute(
            owner=self.user,
            repo_name="test-repo",
            measurement_type=MeasurementName.COVERAGE,
        )

        assert Dataset.objects.filter(
            name=MeasurementName.COVERAGE.value,
            repository_id=self.repo.pk,
        ).exists()

    @patch("services.task.TaskService.backfill_dataset")
    @freeze_time("2022-01-01T00:00:00")
    def test_triggers_task(self, backfill_dataset):
        CommitFactory(repository=self.repo, timestamp=datetime(2000, 1, 1, 1, 1, 1))
        CommitFactory(repository=self.repo, timestamp=datetime(2021, 12, 31, 1, 1, 1))
        self.execute(owner=self.user)
        dataset = Dataset.objects.filter(
            name=MeasurementName.FLAG_COVERAGE.value,
            repository_id=self.repo.pk,
        ).first()
        backfill_dataset.assert_called_once_with(
            dataset,
            start_date=timezone.datetime(2000, 1, 1),
            end_date=timezone.datetime(2022, 1, 1),
        )

    @patch("services.task.TaskService.backfill_dataset")
    def test_no_commits(self, backfill_dataset):
        self.execute(owner=self.user)
        assert backfill_dataset.call_count == 0
