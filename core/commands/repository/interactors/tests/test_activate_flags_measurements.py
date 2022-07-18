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

    def execute(self, user, repo_name=None):
        current_user = user or AnonymousUser()
        return ActivateFlagsMeasurementsInteractor(current_user, "github").execute(
            repo_name=repo_name or "test-repo",
            owner_name="test-org",
        )

    async def test_unauthenticated(self):
        with pytest.raises(Unauthenticated):
            await self.execute(user=None)

    async def test_repo_not_found(self):
        with pytest.raises(ValidationError):
            await self.execute(user=self.user, repo_name="wrong")

    @patch("services.task.TaskService.backfill_repo")
    def test_creates_dataset(self, backfill_repo):
        assert not Dataset.objects.filter(
            name=MeasurementName.FLAG_COVERAGE.value,
            repository_id=self.repo.pk,
        ).exists()

        async_to_sync(self.execute)(user=self.user)

        assert Dataset.objects.filter(
            name=MeasurementName.FLAG_COVERAGE.value,
            repository_id=self.repo.pk,
        ).exists()

    @patch("services.task.TaskService.backfill_repo")
    def test_triggers_task(self, backfill_repo):
        self.execute(user=self.user)
        backfill_repo.assert_called_once
