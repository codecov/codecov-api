from unittest.mock import patch

import pytest
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase
from django.utils import timezone
from freezegun import freeze_time

from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from timeseries.models import Dataset, MeasurementName

from ..activate_flags_measurements import ActivateFlagsMeasurementsInteractor


@pytest.mark.skipif(
    not settings.TIMESERIES_ENABLED, reason="requires timeseries data storage"
)
class ActivateFlagsMeasurementsInteractorTest(TransactionTestCase):
    databases = {"default", "timeseries"}

    def setUp(self):
        self.org = OwnerFactory(username="test-org")
        self.repo = RepositoryFactory(author=self.org, name="test-repo", active=True)
        self.user = OwnerFactory(permission=[self.repo.pk])

    @async_to_sync
    def execute(self, user, repo_name=None):
        current_user = user or AnonymousUser()
        return ActivateFlagsMeasurementsInteractor(current_user, "github").execute(
            repo_name=repo_name or "test-repo",
            owner_name="test-org",
        )

    def test_unauthenticated(self):
        with pytest.raises(Unauthenticated):
            self.execute(user=None)

    def test_repo_not_found(self):
        with pytest.raises(ValidationError):
            self.execute(user=self.user, repo_name="wrong")

    @patch("services.task.TaskService.backfill_repo")
    def test_creates_dataset(self, backfill_repo):
        assert not Dataset.objects.filter(
            name=MeasurementName.FLAG_COVERAGE.value,
            repository_id=self.repo.pk,
        ).exists()

        self.execute(user=self.user)

        assert Dataset.objects.filter(
            name=MeasurementName.FLAG_COVERAGE.value,
            repository_id=self.repo.pk,
        ).exists()

    @patch("services.task.TaskService.backfill_repo")
    @freeze_time("2022-01-01T00:00:00")
    def test_triggers_task(self, backfill_repo):
        self.execute(user=self.user)
        backfill_repo.assert_called_once_with(
            self.repo,
            start_date=timezone.datetime(2000, 1, 1),
            end_date=timezone.datetime(2022, 1, 1, tzinfo=timezone.utc),
        )
