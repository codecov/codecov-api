from unittest.mock import patch

from django.test import TransactionTestCase

from core.tests.factories import CommitFactory, RepositoryFactory
from graphql_api.dataloader.bundle_analysis import (
    load_bundle_analysis_comparison,
    load_bundle_analysis_report,
)
from graphql_api.types.comparison.comparison import MissingBaseReport, MissingHeadReport
from reports.models import CommitReport
from reports.tests.factories import CommitReportFactory


class BundleAnalysisComparisonLoader(TransactionTestCase):
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

    @patch("graphql_api.dataloader.bundle_analysis.BundleAnalysisComparison")
    @patch("graphql_api.dataloader.bundle_analysis.BundleAnalysisReportLoader")
    def test_loader(self, mock_loader, mock_comparison):
        mock_loader.return_value = None
        mock_comparison.return_value = True
        loader = load_bundle_analysis_comparison(self.base_commit, self.head_commit)

        assert loader == True

    def test_loader_missing_base_report(self):
        base_commit = CommitFactory(repository=self.repo)
        CommitReportFactory(
            commit=base_commit, report_type=CommitReport.ReportType.COVERAGE
        )

        loader = load_bundle_analysis_comparison(
            base_commit,
            self.head_commit,
        )
        assert loader.message == MissingBaseReport.message

    def test_loader_missing_head_report(self):
        head_commit = CommitFactory(repository=self.repo)
        CommitReportFactory(
            commit=head_commit, report_type=CommitReport.ReportType.COVERAGE
        )

        loader = load_bundle_analysis_comparison(
            self.base_commit,
            head_commit,
        )
        assert loader.message == MissingHeadReport.message

    def test_loader_no_base_report(self):
        base_commit = CommitFactory(repository=self.repo)

        loader = load_bundle_analysis_comparison(
            base_commit,
            self.head_commit,
        )
        assert loader.message == MissingBaseReport.message

    def test_loader_no_head_report(self):
        head_commit = CommitFactory(repository=self.repo)

        loader = load_bundle_analysis_comparison(
            self.base_commit,
            head_commit,
        )
        assert loader.message == MissingHeadReport.message


class MockReportLoader:
    def load(self, external_id):
        return True


class BundleAnalysisReportLoader(TransactionTestCase):
    def setUp(self):
        self.repo = RepositoryFactory()

        self.commit = CommitFactory(repository=self.repo)
        self.commit_report = CommitReportFactory(
            commit=self.commit, report_type=CommitReport.ReportType.BUNDLE_ANALYSIS
        )

    @patch("graphql_api.dataloader.bundle_analysis.BundleAnalysisReport")
    @patch("graphql_api.dataloader.bundle_analysis.BundleAnalysisReportLoader")
    def test_loader(self, mock_loader, mock_report):
        mock_loader.return_value = MockReportLoader()
        mock_report.return_value = True
        loader = load_bundle_analysis_report(self.commit)
        assert loader == True

    def test_loader_missing_head_report(self):
        head_commit = CommitFactory(repository=self.repo)
        CommitReportFactory(
            commit=head_commit, report_type=CommitReport.ReportType.COVERAGE
        )
        loader = load_bundle_analysis_report(head_commit)
        assert loader.message == MissingHeadReport.message

    def test_loader_no_head_report(self):
        head_commit = CommitFactory(repository=self.repo)
        loader = load_bundle_analysis_report(head_commit)
        assert loader.message == MissingHeadReport.message
