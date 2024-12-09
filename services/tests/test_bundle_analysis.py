from unittest.mock import patch

import pytest
from django.test import TestCase
from shared.api_archive.archive import ArchiveService
from shared.bundle_analysis import BundleAnalysisReport as SharedBundleAnalysisReport
from shared.bundle_analysis import (
    BundleAnalysisReportLoader,
    BundleChange,
    StoragePaths,
)
from shared.bundle_analysis.storage import get_bucket_name
from shared.django_apps.core.tests.factories import CommitFactory, RepositoryFactory
from shared.storage.memory import MemoryStorageService

from reports.models import CommitReport
from reports.tests.factories import CommitReportFactory
from services.bundle_analysis import (
    BundleAnalysisComparison,
    BundleAnalysisReport,
    BundleComparison,
    BundleReport,
    load_report,
)


@pytest.mark.django_db
@patch("services.bundle_analysis.get_appropriate_storage_service")
def test_load_report(get_storage_service):
    storage = MemoryStorageService({})
    get_storage_service.return_value = storage

    repo = RepositoryFactory()
    commit = CommitFactory(repository=repo)

    # no commit report record
    assert load_report(commit) is None

    commit_report = CommitReportFactory(
        commit=commit, report_type=CommitReport.ReportType.BUNDLE_ANALYSIS
    )

    storage_path = StoragePaths.bundle_report.path(
        repo_key=ArchiveService.get_archive_hash(repo),
        report_key=commit_report.external_id,
    )

    # nothing in storage
    assert load_report(commit) is None

    with open("./services/tests/samples/bundle_report.sqlite", "rb") as f:
        storage.write_file(get_bucket_name(), storage_path, f)

    report = load_report(commit)
    assert report is not None
    assert isinstance(report, SharedBundleAnalysisReport)


class TestBundleComparison(TestCase):
    @patch("services.bundle_analysis.SharedBundleChange")
    def test_bundle_comparison(self, mock_shared_bundle_change):
        mock_shared_bundle_change = BundleChange(
            bundle_name="bundle1",
            change_type=BundleChange.ChangeType.ADDED,
            size_delta=1000000,
            percentage_delta=0.0,
        )

        bundle_comparison = BundleComparison(
            mock_shared_bundle_change,
            7654321,
        )

        assert bundle_comparison.bundle_name == "bundle1"
        assert bundle_comparison.change_type == "added"
        assert bundle_comparison.size_delta == 1000000
        assert bundle_comparison.size_total == 7654321


class TestBundleAnalysisComparison(TestCase):
    def setUp(self):
        self.repo = RepositoryFactory()

        self.base_commit = CommitFactory(repository=self.repo)
        self.base_commit_report = CommitReportFactory(
            commit=self.base_commit, report_type=CommitReport.ReportType.BUNDLE_ANALYSIS
        )

        self.head_commit = CommitFactory(repository=self.repo)
        self.head_commit_report = CommitReportFactory(
            commit=self.head_commit, report_type=CommitReport.ReportType.BUNDLE_ANALYSIS
        )

    @patch("services.bundle_analysis.get_appropriate_storage_service")
    def test_bundle_analysis_comparison(self, get_storage_service):
        storage = MemoryStorageService({})
        get_storage_service.return_value = storage

        with open("./services/tests/samples/base_bundle_report.sqlite", "rb") as f:
            storage_path = StoragePaths.bundle_report.path(
                repo_key=ArchiveService.get_archive_hash(self.repo),
                report_key=self.base_commit_report.external_id,
            )
            storage.write_file(get_bucket_name(), storage_path, f)

        with open("./services/tests/samples/head_bundle_report.sqlite", "rb") as f:
            storage_path = StoragePaths.bundle_report.path(
                repo_key=ArchiveService.get_archive_hash(self.repo),
                report_key=self.head_commit_report.external_id,
            )
            storage.write_file(get_bucket_name(), storage_path, f)

        loader = BundleAnalysisReportLoader(
            storage_service=storage,
            repo_key=ArchiveService.get_archive_hash(self.head_commit.repository),
        )

        bac = BundleAnalysisComparison(
            loader,
            self.base_commit_report.external_id,
            self.head_commit_report.external_id,
            self.repo,
        )

        assert len(bac.bundles) == 5
        assert bac.size_delta == 36555
        assert bac.size_total == 201720


class TestBundleReport(TestCase):
    def test_bundle_comparison(self):
        class MockSharedBundleReport:
            def __init__(self, db_path, bundle_name):
                self.bundle_name = bundle_name

            def total_size(self):
                return 7654321

            @property
            def name(self):
                return self.bundle_name

        bundle_comparison = BundleReport(MockSharedBundleReport("123abc", "bundle1"))

        assert bundle_comparison.name == "bundle1"
        assert bundle_comparison.size_total == 7654321


class TestBundleAnalysisReport(TestCase):
    def setUp(self):
        self.repo = RepositoryFactory()

        self.commit = CommitFactory(repository=self.repo)
        self.commit_report = CommitReportFactory(
            commit=self.commit, report_type=CommitReport.ReportType.BUNDLE_ANALYSIS
        )

    @patch("services.bundle_analysis.get_appropriate_storage_service")
    def test_bundle_analysis_report(self, get_storage_service):
        storage = MemoryStorageService({})
        get_storage_service.return_value = storage

        with open("./services/tests/samples/head_bundle_report.sqlite", "rb") as f:
            storage_path = StoragePaths.bundle_report.path(
                repo_key=ArchiveService.get_archive_hash(self.repo),
                report_key=self.commit_report.external_id,
            )
            storage.write_file(get_bucket_name(), storage_path, f)

        loader = BundleAnalysisReportLoader(
            storage_service=storage,
            repo_key=ArchiveService.get_archive_hash(self.commit.repository),
        )

        bar = BundleAnalysisReport(loader.load(self.commit_report.external_id))

        assert len(bar.bundles) == 4
        assert bar.size_total == 201720
