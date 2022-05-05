import asyncio

from django.test import TransactionTestCase

from compare.tests.factories import CommitComparisonFactory
from core.tests.factories import CommitFactory, RepositoryFactory
from graphql_api.dataloader.commit_comparison import CommitComparisonLoader


class GraphQLResolveInfo:
    def __init__(self):
        self.context = {}


class CommitReportLoaderTestCase(TransactionTestCase):
    def setUp(self):
        self.repository = RepositoryFactory(name="test-repo-1")

        self.commit1 = CommitFactory(
            message="commit1", repository=self.repository, commitid="123"
        )
        self.commit2 = CommitFactory(
            message="commit2", repository=self.repository, commitid="234"
        )
        self.comparison1 = CommitComparisonFactory(
            base_commit=self.commit1,
            compare_commit=self.commit2,
        )

        self.commit3 = CommitFactory(
            message="commit3", repository=self.repository, commitid="345"
        )
        self.commit4 = CommitFactory(
            message="commit4", repository=self.repository, commitid="456"
        )
        self.comparison2 = CommitComparisonFactory(
            base_commit=self.commit3,
            compare_commit=self.commit4,
        )

        self.info = GraphQLResolveInfo()

    async def test_one_commit_comparison(self):
        loader = CommitComparisonLoader.loader(self.info)
        commit_comparison = await loader.load(
            (self.commit1.commitid, self.commit2.commitid)
        )
        assert commit_comparison == self.comparison1

    async def test_many_commit_comparisons(self):
        loader = CommitComparisonLoader.loader(self.info)
        commit_comparisons = await asyncio.gather(
            loader.load((self.commit1.commitid, self.commit2.commitid)),
            loader.load((self.commit3.commitid, self.commit4.commitid)),
        )
        assert commit_comparisons == [self.comparison1, self.comparison2]
