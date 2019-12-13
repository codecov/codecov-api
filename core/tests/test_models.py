from django.test import TestCase

from .factories import RepositoryFactory, CommitFactory
from ..models import Repository, Commit


class RepositoryTests(TestCase):
    def setUp(self):
        self.repo = RepositoryFactory()
        self.commit = CommitFactory(repository=self.repo)

    def test_latest_commit_retrieves_latest_commit_in_complete_state(self):
        newer_pending_commit = CommitFactory(repository=self.repo, state=Commit.CommitStates.PENDING)
        assert newer_pending_commit.timestamp > self.commit.timestamp
        assert self.repo.latest_commit == self.commit
