from datetime import datetime
from unittest.mock import patch

import pytz
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from freezegun import freeze_time

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory


class BackfillCommandTest(TestCase):
    databases = {"default", "timeseries"}

    def setUp(self):
        self.owner = OwnerFactory()
        self.repo1 = RepositoryFactory(author=self.owner)
        self.repo2 = RepositoryFactory(author=self.owner)
        self.repo3 = RepositoryFactory()

    @patch(
        "timeseries.management.commands.timeseries_backfill.refresh_measurement_summaries"
    )
    @patch("timeseries.management.commands.timeseries_backfill.save_repo_measurements")
    @freeze_time("2022-06-07")
    def test_call_command_single_repo(
        self, save_repo_measurements, refresh_measurement_summaries
    ):
        call_command(
            "timeseries_backfill",
            start_date="2022-01-01",
            owner=self.owner.username,
            repo=self.repo1.name,
            refresh=True,
        )

        save_repo_measurements.assert_called_once_with(
            self.repo1,
            start_date=datetime(2022, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
            end_date=datetime(2022, 6, 7, 0, 0, 0, tzinfo=pytz.utc),
        )

        refresh_measurement_summaries.assert_called_once_with(
            datetime(2022, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
            datetime(2022, 6, 7, 0, 0, 0, tzinfo=pytz.utc),
        )

    @patch(
        "timeseries.management.commands.timeseries_backfill.refresh_measurement_summaries"
    )
    @patch("timeseries.management.commands.timeseries_backfill.save_repo_measurements")
    def test_call_command_single_repo_end_date(
        self, save_repo_measurements, refresh_measurement_summaries
    ):
        call_command(
            "timeseries_backfill",
            start_date="2022-01-01",
            end_date="2022-01-02",
            owner=self.owner.username,
            repo=self.repo1.name,
            refresh=True,
        )

        save_repo_measurements.assert_called_once_with(
            self.repo1,
            start_date=datetime(2022, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
            end_date=datetime(2022, 1, 2, 0, 0, 0, tzinfo=pytz.utc),
        )

        refresh_measurement_summaries.assert_called_once_with(
            datetime(2022, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
            datetime(2022, 1, 2, 0, 0, 0, tzinfo=pytz.utc),
        )

    @patch(
        "timeseries.management.commands.timeseries_backfill.refresh_measurement_summaries"
    )
    @patch("timeseries.management.commands.timeseries_backfill.save_repo_measurements")
    @freeze_time("2022-06-07")
    def test_call_command_owner_repos(
        self, save_repo_measurements, refresh_measurement_summaries
    ):
        call_command(
            "timeseries_backfill",
            start_date="2022-01-01",
            owner=self.owner.username,
            refresh=True,
        )

        assert save_repo_measurements.call_count == 2
        save_repo_measurements.assert_any_call(
            self.repo1,
            start_date=datetime(2022, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
            end_date=datetime(2022, 6, 7, 0, 0, 0, tzinfo=pytz.utc),
        )
        save_repo_measurements.assert_any_call(
            self.repo2,
            start_date=datetime(2022, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
            end_date=datetime(2022, 6, 7, 0, 0, 0, tzinfo=pytz.utc),
        )

        refresh_measurement_summaries.assert_called_once_with(
            datetime(2022, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
            datetime(2022, 6, 7, 0, 0, 0, tzinfo=pytz.utc),
        )

    def test_call_command_no_start_date(self):
        with self.assertRaises(CommandError):
            call_command(
                "timeseries_backfill",
                owner=self.owner.username,
                repo=self.repo1.name,
            )

    def test_call_command_no_owner(self):
        with self.assertRaises(CommandError):
            call_command(
                "timeseries_backfill",
                start_date="2022-01-01",
            )

    def test_call_command_wrong_owner(self):
        with self.assertRaises(CommandError):
            call_command(
                "timeseries_backfill",
                owner="wrong-owner",
                start_date="2022-01-01",
            )

    def test_call_command_wrong_repo(self):
        with self.assertRaises(CommandError):
            call_command(
                "timeseries_backfill",
                owner=self.owner.username,
                repo=f"wrong-repo",
                start_date="2022-01-01",
            )
