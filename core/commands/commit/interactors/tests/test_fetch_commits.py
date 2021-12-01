from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory

from ..fetch_commits import FetchCommitsInteractor


class FetchCommitsInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org, private=False)
        self.commits = [
            CommitFactory(repository=self.repo),
            CommitFactory(repository=self.repo),
            CommitFactory(repository=self.repo),
        ]
        self.repo_2 = RepositoryFactory(author=self.org, private=False)
        self.commits_2 = [
            CommitFactory(repository=self.repo_2),
            CommitFactory(repository=self.repo_2),
            CommitFactory(repository=self.repo_2, ci_passed=False),
        ]

    # helper to execute the interactor
    def execute(self, user, *args):
        service = user.service if user else "github"
        current_user = user or AnonymousUser()
        return FetchCommitsInteractor(current_user, service).execute(*args)

    def test_fetch_commits(self):
        self.filters = None
        commits = async_to_sync(self.execute)(None, self.repo, self.filters)
        assert list(commits) == self.commits

    def test_fetch_commits_with_failed_ci(self):
        self.filters = {"hide_failed_ci": True}
        commits = async_to_sync(self.execute)(None, self.repo_2, self.filters)
        commits_with_filter = list(
            filter(lambda commit: commit.ci_passed is True, self.commits_2)
        )
        assert list(commits) == commits_with_filter
