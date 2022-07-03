from datetime import datetime, timezone
from unittest.mock import PropertyMock, patch

from django.test import TestCase
from shared.reports.resources import Report, ReportFile, ReportLine
from shared.utils.sessions import Session

from core.tests.factories import CommitFactory, RepositoryFactory
from reports.tests.factories import RepositoryFlagFactory
from timeseries.helpers import (
    refresh_measurement_summaries,
    save_commit_measurements,
    save_repo_measurements,
)
from timeseries.models import Measurement, MeasurementName
from timeseries.tests.factories import MeasurementFactory


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


class SaveRepoMeasurementsTest(TestCase):
    databases = {"default"}

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
