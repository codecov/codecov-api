from datetime import datetime, timezone
from unittest.mock import call, patch

import pytest
from django.conf import settings
from django.test import TestCase
from django.utils import timezone
from shared.reports.resources import Report, ReportFile, ReportLine
from shared.utils.sessions import Session

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory
from reports.tests.factories import RepositoryFlagFactory
from timeseries.helpers import (
    coverage_measurements,
    owner_coverage_measurements_with_fallback,
    refresh_measurement_summaries,
    repository_coverage_measurements_with_fallback,
    save_commit_measurements,
    save_repo_measurements,
)
from timeseries.models import Dataset, Interval, Measurement, MeasurementName
from timeseries.tests.factories import DatasetFactory, MeasurementFactory


def sample_report():
    report = Report()
    first_file = ReportFile("file_1.go")
    first_file.append(
        1, ReportLine.create(coverage=1, sessions=[[0, 1]], complexity=(10, 2))
    )
    first_file.append(2, ReportLine.create(coverage=0, sessions=[[0, 1]]))
    first_file.append(3, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    first_file.append(5, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    first_file.append(6, ReportLine.create(coverage=0, sessions=[[0, 1]]))
    first_file.append(8, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    first_file.append(9, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    first_file.append(10, ReportLine.create(coverage=0, sessions=[[0, 1]]))
    second_file = ReportFile("file_2.py")
    second_file.append(12, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    second_file.append(
        51, ReportLine.create(coverage="1/2", type="b", sessions=[[0, 1]])
    )
    report.append(first_file)
    report.append(second_file)
    report.add_session(Session(flags=["flag1", "flag2"]))
    return report


@pytest.mark.skipif(
    not settings.TIMESERIES_ENABLED, reason="requires timeseries data storage"
)
class SaveCommitMeasurementsTest(TestCase):
    databases = {"default", "timeseries"}

    @patch("services.archive.ReportService.build_report_from_commit")
    def test_insert_commit_measurement(self, mock_report):
        mock_report.return_value = sample_report()

        commit = CommitFactory(branch="foo")
        save_commit_measurements(commit)

        measurement_queryset = Measurement.objects.filter(
            name=MeasurementName.COVERAGE.value,
            commit_sha=commit.commitid,
            timestamp=commit.timestamp,
        )
        assert measurement_queryset.count() == 1

        measurement = measurement_queryset.first()
        assert measurement
        assert measurement.name == MeasurementName.COVERAGE.value
        assert measurement.owner_id == commit.repository.author_id
        assert measurement.repo_id == commit.repository_id
        assert measurement.flag_id == None
        assert measurement.commit_sha == commit.commitid
        assert measurement.timestamp.replace(
            tzinfo=timezone.utc
        ) == commit.timestamp.replace(tzinfo=timezone.utc)
        assert measurement.branch == "foo"
        assert measurement.value == 60.0

    @patch("services.archive.ReportService.build_report_from_commit")
    def test_insert_commit_measurement_no_report(self, mock_report):
        mock_report.return_value = None

        commit = CommitFactory(branch="foo")
        save_commit_measurements(commit)

        measurement_queryset = Measurement.objects.filter(
            name=MeasurementName.COVERAGE.value,
            commit_sha=commit.commitid,
            timestamp=commit.timestamp,
        )
        assert measurement_queryset.count() == 0

    @patch("services.archive.ReportService.build_report_from_commit")
    def test_update_commit_measurement(self, mock_report):
        mock_report.return_value = sample_report()

        commit = CommitFactory(branch="foo")

        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            owner_id=commit.repository.author_id,
            repo_id=commit.repository_id,
            flag_id=None,
            commit_sha=commit.commitid,
            timestamp=commit.timestamp,
            branch="testing",
            value=0,
        )

        save_commit_measurements(commit)

        measurement = Measurement.objects.filter(
            name=MeasurementName.COVERAGE.value,
            commit_sha=commit.commitid,
            timestamp=commit.timestamp,
        ).first()

        assert measurement
        assert measurement.name == MeasurementName.COVERAGE.value
        assert measurement.owner_id == commit.repository.author_id
        assert measurement.repo_id == commit.repository_id
        assert measurement.flag_id == None
        assert measurement.commit_sha == commit.commitid
        assert measurement.timestamp.replace(
            tzinfo=timezone.utc
        ) == commit.timestamp.replace(tzinfo=timezone.utc)
        assert measurement.branch == "foo"
        assert measurement.value == 60.0

    @patch("services.archive.ReportService.build_report_from_commit")
    def test_commit_measurement_insert_flags(self, mock_report):
        mock_report.return_value = sample_report()

        commit = CommitFactory(branch="foo")

        repository_flag1 = RepositoryFlagFactory(
            repository=commit.repository, flag_name="flag1"
        )

        repository_flag2 = RepositoryFlagFactory(
            repository=commit.repository, flag_name="flag2"
        )

        save_commit_measurements(commit)

        measurement = Measurement.objects.filter(
            name=MeasurementName.FLAG_COVERAGE.value,
            commit_sha=commit.commitid,
            timestamp=commit.timestamp,
            flag_id=repository_flag1.pk,
        ).first()

        assert measurement
        assert measurement.name == MeasurementName.FLAG_COVERAGE.value
        assert measurement.owner_id == commit.repository.author_id
        assert measurement.repo_id == commit.repository_id
        assert measurement.flag_id == repository_flag1.pk
        assert measurement.commit_sha == commit.commitid
        assert measurement.timestamp.replace(
            tzinfo=timezone.utc
        ) == commit.timestamp.replace(tzinfo=timezone.utc)
        assert measurement.branch == "foo"
        assert measurement.value == 100.0

        measurement = Measurement.objects.filter(
            name=MeasurementName.FLAG_COVERAGE.value,
            commit_sha=commit.commitid,
            timestamp=commit.timestamp,
            flag_id=repository_flag2.pk,
        ).first()

        assert measurement
        assert measurement.name == MeasurementName.FLAG_COVERAGE.value
        assert measurement.owner_id == commit.repository.author_id
        assert measurement.repo_id == commit.repository_id
        assert measurement.flag_id == repository_flag2.pk
        assert measurement.commit_sha == commit.commitid
        assert measurement.timestamp.replace(
            tzinfo=timezone.utc
        ) == commit.timestamp.replace(tzinfo=timezone.utc)
        assert measurement.branch == "foo"
        assert measurement.value == 100.0

    @patch("services.archive.ReportService.build_report_from_commit")
    def test_commit_measurement_update_flags(self, mock_report):
        mock_report.return_value = sample_report()

        commit = CommitFactory(branch="foo")

        repository_flag1 = RepositoryFlagFactory(
            repository=commit.repository, flag_name="flag1"
        )

        repository_flag2 = RepositoryFlagFactory(
            repository=commit.repository, flag_name="flag2"
        )

        MeasurementFactory(
            name=MeasurementName.FLAG_COVERAGE.value,
            owner_id=commit.repository.author_id,
            repo_id=commit.repository_id,
            flag_id=repository_flag1.pk,
            commit_sha=commit.commitid,
            timestamp=commit.timestamp,
            branch="testing",
            value=0,
        )

        MeasurementFactory(
            name=MeasurementName.FLAG_COVERAGE.value,
            owner_id=commit.repository.author_id,
            repo_id=commit.repository_id,
            flag_id=repository_flag2.pk,
            commit_sha=commit.commitid,
            timestamp=commit.timestamp,
            branch="testing",
            value=0,
        )

        save_commit_measurements(commit)

        measurement = Measurement.objects.filter(
            name=MeasurementName.FLAG_COVERAGE.value,
            commit_sha=commit.commitid,
            timestamp=commit.timestamp,
            flag_id=repository_flag1.pk,
        ).first()

        assert measurement
        assert measurement.name == MeasurementName.FLAG_COVERAGE.value
        assert measurement.owner_id == commit.repository.author_id
        assert measurement.repo_id == commit.repository_id
        assert measurement.flag_id == repository_flag1.pk
        assert measurement.commit_sha == commit.commitid
        assert measurement.timestamp.replace(
            tzinfo=timezone.utc
        ) == commit.timestamp.replace(tzinfo=timezone.utc)
        assert measurement.branch == "foo"
        assert measurement.value == 100.0

        measurement = Measurement.objects.filter(
            name=MeasurementName.FLAG_COVERAGE.value,
            commit_sha=commit.commitid,
            timestamp=commit.timestamp,
            flag_id=repository_flag2.pk,
        ).first()

        assert measurement
        assert measurement.name == MeasurementName.FLAG_COVERAGE.value
        assert measurement.owner_id == commit.repository.author_id
        assert measurement.repo_id == commit.repository_id
        assert measurement.flag_id == repository_flag2.pk
        assert measurement.commit_sha == commit.commitid
        assert measurement.timestamp.replace(
            tzinfo=timezone.utc
        ) == commit.timestamp.replace(tzinfo=timezone.utc)
        assert measurement.branch == "foo"
        assert measurement.value == 100.0


@pytest.mark.skipif(
    not settings.TIMESERIES_ENABLED, reason="requires timeseries data storage"
)
class SaveRepoMeasurementsTest(TestCase):
    databases = {"default", "timeseries"}

    def setUp(self):
        self.repo = RepositoryFactory()
        self.commit1 = CommitFactory(
            repository=self.repo, timestamp=datetime(2022, 1, 1, 0, 0, 0)
        )
        self.commit2 = CommitFactory(
            repository=self.repo, timestamp=datetime(2022, 1, 2, 0, 0, 0)
        )
        self.commit3 = CommitFactory(
            repository=self.repo, timestamp=datetime(2022, 1, 3, 0, 0, 0)
        )
        self.commit4 = CommitFactory(
            repository=self.repo, timestamp=datetime(2022, 1, 4, 0, 0, 0)
        )

    @patch("timeseries.helpers.save_commit_measurements")
    def test_save_repo_measurements(self, save_commit_measurements):
        save_repo_measurements(
            self.repo,
            start_date=datetime(2022, 1, 2, 0, 0, 0),
            end_date=datetime(2022, 1, 3, 0, 0, 0),
        )

        assert save_commit_measurements.call_count == 2
        save_commit_measurements.assert_any_call(self.commit2)
        save_commit_measurements.assert_any_call(self.commit3)

        coverage_dataset = Dataset.objects.get(
            name=MeasurementName.COVERAGE.value, repository_id=self.repo.pk
        )
        assert coverage_dataset.backfilled

        flag_coverage_dataset = Dataset.objects.get(
            name=MeasurementName.FLAG_COVERAGE.value, repository_id=self.repo.pk
        )
        assert flag_coverage_dataset.backfilled


@pytest.mark.skipif(
    not settings.TIMESERIES_ENABLED, reason="requires timeseries data storage"
)
class RefreshMeasurementSummariesTest(TestCase):
    databases = {"timeseries"}

    @patch("django.db.backends.utils.CursorWrapper.execute")
    def test_refresh_measurement_summaries(self, execute):
        refresh_measurement_summaries(
            start_date=datetime(2022, 1, 1, 0, 0, 0),
            end_date=datetime(2022, 1, 2, 0, 0, 0),
        )

        assert execute.call_count == 3
        sql_statements = [call[0][0] for call in execute.call_args_list]
        assert sql_statements == [
            "CALL refresh_continuous_aggregate('timeseries_measurement_summary_1day', '2022-01-01T00:00:00', '2022-01-02T00:00:00')",
            "CALL refresh_continuous_aggregate('timeseries_measurement_summary_7day', '2022-01-01T00:00:00', '2022-01-02T00:00:00')",
            "CALL refresh_continuous_aggregate('timeseries_measurement_summary_30day', '2022-01-01T00:00:00', '2022-01-02T00:00:00')",
        ]


@pytest.mark.skipif(
    not settings.TIMESERIES_ENABLED, reason="requires timeseries data storage"
)
class RepositoryCoverageMeasurementsTest(TestCase):
    databases = {"default", "timeseries"}

    def setUp(self):
        self.repo = RepositoryFactory()

        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            owner_id=self.repo.author_id,
            repo_id=self.repo.pk,
            timestamp=datetime(2022, 1, 1, 1, 0, 0),
            value=80.0,
            branch="master",
            commit_sha="commit1",
        )
        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            owner_id=self.repo.author_id,
            repo_id=self.repo.pk,
            timestamp=datetime(2022, 1, 1, 2, 0, 0),
            value=85.0,
            branch="master",
            commit_sha="commit2",
        )
        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            owner_id=self.repo.author_id,
            repo_id=self.repo.pk,
            timestamp=datetime(2022, 1, 1, 3, 0, 0),
            value=90.0,
            branch="other",
            commit_sha="commit3",
        )
        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            owner_id=self.repo.author_id,
            repo_id=self.repo.pk,
            timestamp=datetime(2022, 1, 2, 1, 0, 0),
            value=80.0,
            branch="master",
            commit_sha="commit4",
        )

    def test_coverage_measurements(self):
        res = coverage_measurements(
            Interval.INTERVAL_1_DAY,
            start_date=datetime(2021, 12, 30, 0, 0, 0),
            end_date=datetime(2022, 1, 4, 0, 0, 0),
            repo_id=self.repo.pk,
            branch=self.repo.branch,
        )
        assert list(res) == [
            {
                # aggregates over 2 measurements on main branch (commit1, commit2)
                "timestamp_bin": datetime(2022, 1, 1, 0, 0, tzinfo=timezone.utc),
                "avg": 82.5,
                "min": 80.0,
                "max": 85.0,
            },
            {
                # aggregates over 1 measurement (commit4)
                "timestamp_bin": datetime(2022, 1, 2, 0, 0, tzinfo=timezone.utc),
                "avg": 80.0,
                "min": 80.0,
                "max": 80.0,
            },
        ]


@pytest.mark.skipif(
    not settings.TIMESERIES_ENABLED, reason="requires timeseries data storage"
)
class RepositoryCoverageMeasurementsWithFallbackTest(TestCase):
    databases = {"default", "timeseries"}

    def setUp(self):
        self.repo = RepositoryFactory()

    @patch("timeseries.models.Dataset.is_backfilled")
    def test_backfilled_dataset(self, is_backfilled):
        is_backfilled.return_value = True

        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            owner_id=self.repo.author_id,
            repo_id=self.repo.pk,
            timestamp=datetime(2022, 1, 1, 1, 0, 0),
            value=80.0,
            branch="master",
            commit_sha="commit1",
        )
        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            owner_id=self.repo.author_id,
            repo_id=self.repo.pk,
            timestamp=datetime(2022, 1, 1, 2, 0, 0),
            value=85.0,
            branch="master",
            commit_sha="commit2",
        )
        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            owner_id=self.repo.author_id,
            repo_id=self.repo.pk,
            timestamp=datetime(2022, 1, 1, 3, 0, 0),
            value=90.0,
            branch="other",
            commit_sha="commit3",
        )
        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            owner_id=self.repo.author_id,
            repo_id=self.repo.pk,
            timestamp=datetime(2022, 1, 2, 1, 0, 0),
            value=80.0,
            branch="master",
            commit_sha="commit4",
        )

        DatasetFactory(
            name=MeasurementName.COVERAGE.value,
            repository_id=self.repo.pk,
        )

        res = repository_coverage_measurements_with_fallback(
            self.repo,
            Interval.INTERVAL_1_DAY,
            start_date=datetime(2021, 12, 31, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2022, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
        )
        assert list(res) == [
            {
                # aggregates over 2 measurements on main branch (commit1, commit2)
                "timestamp_bin": datetime(2022, 1, 1, 0, 0, tzinfo=timezone.utc),
                "avg": 82.5,
                "min": 80.0,
                "max": 85.0,
            },
            {
                # aggregates over 1 measurement (commit4)
                "timestamp_bin": datetime(2022, 1, 2, 0, 0, tzinfo=timezone.utc),
                "avg": 80.0,
                "min": 80.0,
                "max": 80.0,
            },
        ]

    @patch("timeseries.models.Dataset.is_backfilled")
    def test_unbackfilled_dataset(self, is_backfilled):
        is_backfilled.return_value = False

        CommitFactory(
            commitid="commit1",
            repository_id=self.repo.pk,
            branch="master",
            timestamp=datetime(2022, 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            totals={
                "c": "80.00",
            },
        )
        CommitFactory(
            commitid="commit2",
            repository_id=self.repo.pk,
            branch="master",
            timestamp=datetime(2022, 1, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
            totals={"c": "85.00"},
        )
        CommitFactory(
            commitid="commit3",
            repository_id=self.repo.pk,
            branch="other",
            timestamp=datetime(2022, 1, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
            totals={"c": "90.00"},
        )
        CommitFactory(
            commitid="commit4",
            repository_id=self.repo.pk,
            branch="master",
            timestamp=datetime(2022, 1, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
            totals={
                "c": "80.00",
            },
        )

        DatasetFactory(
            name=MeasurementName.COVERAGE.value,
            repository_id=self.repo.pk,
        )

        res = repository_coverage_measurements_with_fallback(
            self.repo,
            Interval.INTERVAL_1_DAY,
            start_date=datetime(2021, 12, 31, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2022, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
        )
        assert list(res) == [
            {
                # aggregates over 2 measurements on main branch (commit1, commit2)
                "timestamp_bin": datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "avg": 82.5,
                "min": 80.0,
                "max": 85.0,
            },
            {
                # aggregates over 1 measurement (commit4)
                "timestamp_bin": datetime(2022, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
                "avg": 80.0,
                "min": 80.0,
                "max": 80.0,
            },
        ]

    @patch("timeseries.helpers.trigger_backfill")
    def test_no_dataset(self, trigger_backfill):
        CommitFactory(
            commitid="commit1",
            repository_id=self.repo.pk,
            branch="master",
            timestamp=datetime(2022, 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            totals={
                "c": "80.00",
            },
        )
        CommitFactory(
            commitid="commit2",
            repository_id=self.repo.pk,
            branch="master",
            timestamp=datetime(2022, 1, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
            totals={"c": "85.00"},
        )
        CommitFactory(
            commitid="commit3",
            repository_id=self.repo.pk,
            branch="other",
            timestamp=datetime(2022, 1, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
            totals={"c": "90.00"},
        )
        CommitFactory(
            commitid="commit4",
            repository_id=self.repo.pk,
            branch="master",
            timestamp=datetime(2022, 1, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
            totals={
                "c": "80.00",
            },
        )

        res = repository_coverage_measurements_with_fallback(
            self.repo,
            Interval.INTERVAL_1_DAY,
            start_date=datetime(2021, 12, 31, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2022, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
        )
        assert list(res) == [
            {
                # aggregates over 2 measurements on main branch (commit1, commit2)
                "timestamp_bin": datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "avg": 82.5,
                "min": 80.0,
                "max": 85.0,
            },
            {
                # aggregates over 1 measurement (commit4)
                "timestamp_bin": datetime(2022, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
                "avg": 80.0,
                "min": 80.0,
                "max": 80.0,
            },
        ]

        dataset = Dataset.objects.filter(
            name=MeasurementName.COVERAGE.value,
            repository_id=self.repo.pk,
        ).first()
        assert dataset
        trigger_backfill.assert_called_once_with(dataset)


@pytest.mark.skipif(
    not settings.TIMESERIES_ENABLED, reason="requires timeseries data storage"
)
class OwnerCoverageMeasurementsWithFallbackTest(TestCase):
    databases = {"default", "timeseries"}

    def setUp(self):
        self.owner = OwnerFactory()
        self.repo1 = RepositoryFactory(author=self.owner)
        self.repo2 = RepositoryFactory(author=self.owner)

    @patch("timeseries.models.Dataset.is_backfilled")
    def test_backfilled_datasets(self, is_backfilled):
        is_backfilled.return_value = True

        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            owner_id=self.repo1.author_id,
            repo_id=self.repo1.pk,
            timestamp=datetime(2022, 1, 1, 1, 0, 0),
            value=80.0,
            branch="master",
            commit_sha="commit1",
        )
        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            owner_id=self.repo1.author_id,
            repo_id=self.repo1.pk,
            timestamp=datetime(2022, 1, 1, 2, 0, 0),
            value=85.0,
            branch="master",
            commit_sha="commit2",
        )
        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            owner_id=self.repo1.author_id,
            repo_id=self.repo1.pk,
            timestamp=datetime(2022, 1, 1, 3, 0, 0),
            value=90.0,
            branch="other",
            commit_sha="commit3",
        )
        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            owner_id=self.repo1.author_id,
            repo_id=self.repo1.pk,
            timestamp=datetime(2022, 1, 2, 1, 0, 0),
            value=80.0,
            branch="master",
            commit_sha="commit4",
        )

        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            owner_id=self.repo2.author_id,
            repo_id=self.repo2.pk,
            timestamp=datetime(2022, 1, 1, 1, 0, 0),
            value=80.0,
            branch="master",
            commit_sha="commit1",
        )
        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            owner_id=self.repo2.author_id,
            repo_id=self.repo2.pk,
            timestamp=datetime(2022, 1, 1, 2, 0, 0),
            value=85.0,
            branch="master",
            commit_sha="commit2",
        )
        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            owner_id=self.repo2.author_id,
            repo_id=self.repo2.pk,
            timestamp=datetime(2022, 1, 1, 3, 0, 0),
            value=90.0,
            branch="other",
            commit_sha="commit3",
        )
        MeasurementFactory(
            name=MeasurementName.COVERAGE.value,
            owner_id=self.repo2.author_id,
            repo_id=self.repo2.pk,
            timestamp=datetime(2022, 1, 2, 1, 0, 0),
            value=90.0,
            branch="master",
            commit_sha="commit4",
        )

        DatasetFactory(
            name=MeasurementName.COVERAGE.value,
            repository_id=self.repo1.pk,
        )
        DatasetFactory(
            name=MeasurementName.COVERAGE.value,
            repository_id=self.repo2.pk,
        )

        res = owner_coverage_measurements_with_fallback(
            owner=self.owner,
            repo_ids=[self.repo1.pk, self.repo2.pk],
            interval=Interval.INTERVAL_1_DAY,
            start_date=datetime(2021, 12, 31, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2022, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
        )
        assert list(res) == [
            {
                # aggregates over 3 measurements on all branches
                "timestamp_bin": datetime(2022, 1, 1, 0, 0, tzinfo=timezone.utc),
                "avg": 85.0,
                "min": 80.0,
                "max": 90.0,
            },
            {
                # aggregates over 1 measurement (commit4)
                "timestamp_bin": datetime(2022, 1, 2, 0, 0, tzinfo=timezone.utc),
                "avg": 85.0,
                "min": 80.0,
                "max": 90.0,
            },
        ]
        res = owner_coverage_measurements_with_fallback(
            owner=self.owner,
            repo_ids=[self.repo1.pk],
            interval=Interval.INTERVAL_1_DAY,
            start_date=datetime(2021, 12, 31, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2022, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
        )
        assert list(res) == [
            {
                # aggregates over 3 measurements on all branches
                "timestamp_bin": datetime(2022, 1, 1, 0, 0, tzinfo=timezone.utc),
                "avg": 85.0,
                "min": 80.0,
                "max": 90.0,
            },
            {
                # aggregates over 1 measurement (commit4)
                "timestamp_bin": datetime(2022, 1, 2, 0, 0, tzinfo=timezone.utc),
                "avg": 80.0,
                "min": 80.0,
                "max": 80.0,
            },
        ]

    @patch("timeseries.models.Dataset.is_backfilled")
    def test_unbackfilled_dataset(self, is_backfilled):
        is_backfilled.return_value = False

        CommitFactory(
            commitid="commit1",
            repository_id=self.repo1.pk,
            branch="master",
            timestamp=datetime(2022, 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            totals={
                "c": "80.00",
            },
        )
        CommitFactory(
            commitid="commit2",
            repository_id=self.repo1.pk,
            branch="master",
            timestamp=datetime(2022, 1, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
            totals={"c": "85.00"},
        )
        CommitFactory(
            commitid="commit3",
            repository_id=self.repo1.pk,
            branch="other",
            timestamp=datetime(2022, 1, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
            totals={"c": "90.00"},
        )
        CommitFactory(
            commitid="commit4",
            repository_id=self.repo1.pk,
            branch="master",
            timestamp=datetime(2022, 1, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
            totals={
                "c": "80.00",
            },
        )

        CommitFactory(
            commitid="commit1",
            repository_id=self.repo2.pk,
            branch="master",
            timestamp=datetime(2022, 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            totals={
                "c": "80.00",
            },
        )
        CommitFactory(
            commitid="commit2",
            repository_id=self.repo2.pk,
            branch="master",
            timestamp=datetime(2022, 1, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
            totals={"c": "85.00"},
        )
        CommitFactory(
            commitid="commit3",
            repository_id=self.repo2.pk,
            branch="other",
            timestamp=datetime(2022, 1, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
            totals={"c": "90.00"},
        )
        CommitFactory(
            commitid="commit4",
            repository_id=self.repo2.pk,
            branch="master",
            timestamp=datetime(2022, 1, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
            totals={
                "c": "90.00",
            },
        )

        DatasetFactory(
            name=MeasurementName.COVERAGE.value,
            repository_id=self.repo1.pk,
        )
        DatasetFactory(
            name=MeasurementName.COVERAGE.value,
            repository_id=self.repo2.pk,
        )

        res = owner_coverage_measurements_with_fallback(
            owner=self.owner,
            repo_ids=[self.repo1.pk, self.repo2.pk],
            interval=Interval.INTERVAL_1_DAY,
            start_date=datetime(2021, 12, 31, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2022, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
        )
        assert list(res) == [
            {
                # aggregates over 3 commits on all branches
                "timestamp_bin": datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "avg": 85.0,
                "min": 80.0,
                "max": 90.0,
            },
            {
                # aggregates over 1 commit (commit4)
                "timestamp_bin": datetime(2022, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
                "avg": 85.0,
                "min": 80.0,
                "max": 90.0,
            },
        ]
        res = owner_coverage_measurements_with_fallback(
            owner=self.owner,
            repo_ids=[self.repo1.pk],
            interval=Interval.INTERVAL_1_DAY,
            start_date=datetime(2021, 12, 31, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2022, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
        )
        assert list(res) == [
            {
                # aggregates over 3 commits on all branches
                "timestamp_bin": datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "avg": 85.0,
                "min": 80.0,
                "max": 90.0,
            },
            {
                # aggregates over 1 commit (commit4)
                "timestamp_bin": datetime(2022, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
                "avg": 80.0,
                "min": 80.0,
                "max": 80.0,
            },
        ]

    @patch("timeseries.helpers.trigger_backfill")
    def test_no_dataset(self, trigger_backfill):
        CommitFactory(
            commitid="commit1",
            repository_id=self.repo1.pk,
            branch="master",
            timestamp=datetime(2022, 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            totals={
                "c": "80.00",
            },
        )
        CommitFactory(
            commitid="commit2",
            repository_id=self.repo1.pk,
            branch="master",
            timestamp=datetime(2022, 1, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
            totals={"c": "85.00"},
        )
        CommitFactory(
            commitid="commit3",
            repository_id=self.repo1.pk,
            branch="other",
            timestamp=datetime(2022, 1, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
            totals={"c": "90.00"},
        )
        CommitFactory(
            commitid="commit4",
            repository_id=self.repo1.pk,
            branch="master",
            timestamp=datetime(2022, 1, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
            totals={
                "c": "80.00",
            },
        )

        CommitFactory(
            commitid="commit1",
            repository_id=self.repo2.pk,
            branch="master",
            timestamp=datetime(2022, 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            totals={
                "c": "80.00",
            },
        )
        CommitFactory(
            commitid="commit2",
            repository_id=self.repo2.pk,
            branch="master",
            timestamp=datetime(2022, 1, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
            totals={"c": "85.00"},
        )
        CommitFactory(
            commitid="commit3",
            repository_id=self.repo2.pk,
            branch="other",
            timestamp=datetime(2022, 1, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
            totals={"c": "90.00"},
        )
        CommitFactory(
            commitid="commit4",
            repository_id=self.repo2.pk,
            branch="master",
            timestamp=datetime(2022, 1, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
            totals={
                "c": "90.00",
            },
        )

        res = owner_coverage_measurements_with_fallback(
            owner=self.owner,
            repo_ids=[self.repo1.pk, self.repo2.pk],
            interval=Interval.INTERVAL_1_DAY,
            start_date=datetime(2021, 12, 31, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2022, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
        )
        assert list(res) == [
            {
                # aggregates over 3 commits on all branches
                "timestamp_bin": datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "avg": 85.0,
                "min": 80.0,
                "max": 90.0,
            },
            {
                # aggregates over 1 measurement (commit4)
                "timestamp_bin": datetime(2022, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
                "avg": 85.0,
                "min": 80.0,
                "max": 90.0,
            },
        ]

        datasets = Dataset.objects.filter(
            name=MeasurementName.COVERAGE.value,
            repository_id__in=[self.repo1.pk, self.repo2.pk],
        )
        assert datasets.count() == 2
        trigger_backfill.assert_has_calls(
            [call(datasets[0]), call(datasets[1])], any_order=True
        )

        res = owner_coverage_measurements_with_fallback(
            owner=self.owner,
            repo_ids=[self.repo1.pk],
            interval=Interval.INTERVAL_1_DAY,
            start_date=datetime(2021, 12, 31, 0, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2022, 1, 3, 0, 0, 0, tzinfo=timezone.utc),
        )
        assert list(res) == [
            {
                # aggregates over 3 commits on all branches
                "timestamp_bin": datetime(2022, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                "avg": 85.0,
                "min": 80.0,
                "max": 90.0,
            },
            {
                # aggregates over 1 measurement (commit4)
                "timestamp_bin": datetime(2022, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
                "avg": 80.0,
                "min": 80.0,
                "max": 80.0,
            },
        ]
