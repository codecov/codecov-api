from django.test import TransactionTestCase

from core.tests.factories import CommitFactory, PullFactory, RepositoryFactory
from graphql_api.dataloader.commit import CommitLoader


class GraphQLResolveInfo:
    def __init__(self):
        self.context = {}


class CommitLoaderTestCase(TransactionTestCase):
    def setUp(self):
        self.repository = RepositoryFactory(name="test-repo-1")
        self.pull_1_commit = CommitFactory(
            message="pull-1-head", repository=self.repository, commitid="123"
        )
        self.pull_3_commits = [
            CommitFactory(
                message="pull-3-commit-1", repository=self.repository, commitid="456"
            ),
            CommitFactory(
                message="pull-3-commit-2", repository=self.repository, commitid="231"
            ),
            CommitFactory(
                message="pull-3-head", repository=self.repository, commitid="159"
            ),
        ]
        self.pull_2_commits = [
            CommitFactory(
                message="pull-2-commit-1", repository=self.repository, commitid="153"
            ),
            CommitFactory(
                message="pull-2-head", repository=self.repository, commitid="164"
            ),
        ]
        self.base_commit = CommitFactory(
            message="base-commit", repository=self.repository, commitid="346"
        )
        self.pulls = [
            PullFactory(
                pullid=11,
                repository=self.repository,
                title="test-pull-request-1",
                head=self.pull_1_commit.commitid,
                base=self.base_commit.commitid,
            ),
            PullFactory(
                pullid=12,
                repository=self.repository,
                title="test-pull-request-2",
                head=self.pull_3_commits[2].commitid,
                base=self.base_commit.commitid,
            ),
            PullFactory(
                pullid=13,
                repository=self.repository,
                title="test-pull-request-3",
                head=self.pull_2_commits[1].commitid,
                base=self.base_commit.commitid,
            ),
        ]
        self.info = GraphQLResolveInfo()

    async def test_pull_with_one_commit(self):
        loader = CommitLoader.loader(self.info, self.pulls[0].repository_id)
        commit = await loader.load(self.pulls[0].head)
        assert commit == self.pull_1_commit

    async def test_pull_with_many_commit(self):
        loader = CommitLoader.loader(self.info, self.pulls[1].repository_id)
        commit = await loader.load(self.pulls[1].head)
        assert commit == self.pull_3_commits[2]

    async def test_pull_base_commit(self):
        loader = CommitLoader.loader(self.info, self.pulls[0].repository_id)
        commit = await loader.load(self.pulls[0].base)
        assert commit == self.base_commit

    async def test_on_multiple_pulls_commit(self):
        loader = CommitLoader.loader(self.info, self.pulls[1].repository_id)
        commit = await loader.load(self.pulls[1].base)
        assert commit == self.base_commit

        loader = CommitLoader.loader(self.info, self.pulls[2].repository_id)
        commit_2 = await loader.load(self.pulls[2].base)
        assert commit_2 == self.base_commit

    async def test_repeated_commit_in_(self):
        loader = CommitLoader.loader(self.info, self.pulls[1].repository_id)
        commit = await loader.load(self.pulls[1].base)
        assert commit == self.base_commit

        loader = CommitLoader.loader(self.info, self.pulls[2].repository_id)
        commit_2 = await loader.load(self.pulls[2].base)
        assert commit_2 == self.base_commit
