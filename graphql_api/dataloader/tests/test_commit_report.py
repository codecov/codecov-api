import asyncio

from django.test import TransactionTestCase

from core.tests.factories import CommitFactory, RepositoryFactory
from graphql_api.dataloader.commit_report import CommitReportLoader
from reports.tests.factories import CommitReportFactory, ReportLevelTotalsFactory


class GraphQLResolveInfo:
    def __init__(self):
        self.context = {}


class CommitReportLoaderTestCase(TransactionTestCase):
    def setUp(self):
        self.repository = RepositoryFactory(name="test-repo-1")
        self.commit1 = CommitFactory(
            message="commit1", repository=self.repository, commitid="123"
        )
        self.report1 = CommitReportFactory(commit=self.commit1)
        self.report_totals1 = ReportLevelTotalsFactory(
            report=self.report1, coverage=12.34
        )

        self.commit2 = CommitFactory(
            message="commit2", repository=self.repository, commitid="456"
        )
        self.report2 = CommitReportFactory(commit=self.commit2)
        self.report_totals2 = ReportLevelTotalsFactory(
            report=self.report2, coverage=23.45
        )

        self.info = GraphQLResolveInfo()

    async def test_one_commit_report(self):
        loader = CommitReportLoader.loader(self.info)
        commit_report = await loader.load(self.commit1.id)
        assert commit_report == self.report1

    async def test_many_commit_reports(self):
        loader = CommitReportLoader.loader(self.info)
        commit_reports = await asyncio.gather(
            loader.load(self.commit1.id), loader.load(self.commit2.id)
        )
        assert commit_reports == [self.report1, self.report2]
