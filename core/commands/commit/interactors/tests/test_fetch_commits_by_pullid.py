from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, PullFactory, RepositoryFactory

from ..fetch_commits_by_pullid import FetchCommitsByPullidInteractor


class FetchCommitsInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org, private=False)
        self.pull_1 = PullFactory(pullid=2, repository_id=self.repo.repoid,)
        self.pull_2 = PullFactory(pullid=3, repository_id=self.repo.repoid,)
        self.commits_pr_1 = [
            CommitFactory(repository=self.repo, pullid=self.pull_1.pullid),
            CommitFactory(repository=self.repo, pullid=self.pull_1.pullid),
        ]
        self.commits_pr_2 = []

    # helper to execute the interactor
    def execute(self, user, pull, *args):
        service = user.service if user else "github"
        current_user = user or AnonymousUser()
        return FetchCommitsByPullidInteractor(current_user, service).execute(
            pull, *args
        )

    def test_fetch_commits_by_pullid(self):
        commits = async_to_sync(self.execute)(None, self.pull_1)
        assert list(commits) == self.commits_pr_1

    def test_fetch_commits_by_pullid_no_commits(self):
        commits = async_to_sync(self.execute)(None, self.pull_2)
        assert list(commits) == self.commits_pr_2
