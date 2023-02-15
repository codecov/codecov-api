from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from timeseries.tests.factories import DatasetFactory


@pytest.mark.skipif(
    not settings.TIMESERIES_ENABLED, reason="requires timeseries data storage"
)
class DatasetAdminTest(TransactionTestCase):
    databases = {"default", "timeseries"}

    def setUp(self):
        self.owner = OwnerFactory(staff=True)
        self.client.force_login(user=self.owner)

        self.repo1 = RepositoryFactory()
        self.repo2 = RepositoryFactory()
        self.dataset1 = DatasetFactory(repository_id=self.repo1.pk, backfilled=True)
        self.dataset2 = DatasetFactory(repository_id=self.repo2.pk, backfilled=True)

    def test_list_page(self):
        res = self.client.get(reverse(f"admin:timeseries_dataset_changelist"))
        assert res.status_code == 200

    def test_backfill_page(self):
        res = self.client.post(
            reverse("admin:timeseries_dataset_changelist"),
            {
                "action": "backfill",
                ACTION_CHECKBOX_NAME: [
                    self.dataset1.pk,
                    self.dataset2.pk,
                ],
            },
        )
        assert res.status_code == 200
        assert "Backfill will be performed for the following datasets" in str(
            res.content
        )

    @patch("services.task.TaskService.backfill_dataset")
    def test_perform_backfill(self, backfill_dataset):
        res = self.client.post(
            reverse("admin:timeseries_dataset_changelist"),
            {
                "action": "backfill",
                ACTION_CHECKBOX_NAME: [
                    self.dataset1.pk,
                    self.dataset2.pk,
                ],
                "start_date": "2000-01-01",
                "end_date": "2022-01-01",
                "backfill": True,
            },
        )
        assert res.status_code == 302

        backfill_dataset.call_count == 2
        backfill_dataset.assert_any_call(
            self.dataset1,
            start_date=timezone.datetime(2000, 1, 1, tzinfo=timezone.utc),
            end_date=timezone.datetime(2022, 1, 1, tzinfo=timezone.utc),
        )
        backfill_dataset.assert_any_call(
            self.dataset2,
            start_date=timezone.datetime(2000, 1, 1, tzinfo=timezone.utc),
            end_date=timezone.datetime(2022, 1, 1, tzinfo=timezone.utc),
        )

        self.dataset1.refresh_from_db()
        assert self.dataset1.backfilled == False
        self.dataset2.refresh_from_db()
        assert self.dataset2.backfilled == False
