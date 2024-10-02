from unittest.mock import patch

from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import CommitFactory, RepositoryFactory

from graphql_api.dataloader.bundle_analysis import (
    MissingBaseReportError,
    MissingHeadReportError,
    load_bundle_analysis_comparison,
    load_bundle_analysis_report,
)
from graphql_api.types.comparison.comparison import MissingBaseReport, MissingHeadReport
from reports.models import CommitReport
from reports.tests.factories import CommitReportFactory


class MockReportLoader:
    def load(self, external_id):
        return True


class MockReportLoaderTwo:
    def load(self, external_id):
        return None


class MockBundleAnalysisLoaderServiceMissingHeadReport:
    """
    During construction of the Comparison the shared code may raise an exception
    when accessing head_report if it is not available
    """

    def __init__(self):
        raise MissingHeadReportError()


class MockBundleAnalysisLoaderServiceMissingBaseReport:
    """
    During construction of the Comparison the shared code may raise an exception
    when accessing base_report if it is not available
    """

    def __init__(self):
        raise MissingBaseReportError()


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

    def test_loader_raises_missing_head_report(self):
        with patch(
            "graphql_api.dataloader.bundle_analysis.BundleAnalysisComparison",
            side_effect=MissingHeadReportError(),
        ):
            loader = load_bundle_analysis_comparison(self.base_commit, self.head_commit)
            assert loader.message == MissingHeadReport.message

    def test_loader_raises_missing_base_report(self):
        with patch(
            "graphql_api.dataloader.bundle_analysis.BundleAnalysisComparison",
            side_effect=MissingBaseReportError(),
        ):
            loader = load_bundle_analysis_comparison(self.base_commit, self.head_commit)
            assert loader.message == MissingBaseReport.message


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

    @patch("graphql_api.dataloader.bundle_analysis.BundleAnalysisReportLoader")
    def test_loader_missing_head_report_two(self, mock_loader):
        mock_loader.return_value = MockReportLoaderTwo()
        loader = load_bundle_analysis_report(self.commit)
        assert loader.message == MissingHeadReport.message

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
