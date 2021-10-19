import asyncio
from django.test import TestCase, TransactionTestCase

from core.tests.factories import CommitFactory, RepositoryFactory, PullFactory
from graphql_api.dataloader.totals import load_totals_by_id


class GraphQLResolveInfo():
    def __init__(self):
        self.context = {}


class TotalsLoaderTestCase(TransactionTestCase):
    def setUp(self):
        self.repository = RepositoryFactory(name="test-repo")
        self.commit_with_totals = CommitFactory(repository=self.repository, totals = {
            "C": 0,
            "M": 0,
            "N": 0,
            "b": 0,
            "c": "93.00000",
            "d": 0,
            "diff": [1, 2, 1, 1, 0, "50.00000", 0, 0, 0, 0, 0, 0, 0],
            "f": 3,
            "h": 17,
            "m": 3,
            "n": 20,
            "p": 0,
            "s": 1,
        })
        self.info = GraphQLResolveInfo()

    # async def test_commits_with_totals(self):
    #     totals = await load_totals_by_id(self.info, self.commit_with_totals.commitid, self.commit_with_totals.repository_id)
    #     print("totals!")
    #     print(totals)

