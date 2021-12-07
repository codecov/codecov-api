import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory

from ..fetch_commit import FetchCommitInteractor


class FetchCommitInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org, private=False)
        self.commit = CommitFactory(repository=self.repo)

    # helper to execute the interactor
    def execute(self, user, *args):
        service = user.service if user else "github"
        current_user = user or AnonymousUser()
        return FetchCommitInteractor(current_user, service).execute(*args)

    async def test_fetch_commit(self):
        commit = await self.execute(None, self.repo, self.commit.commitid)
        assert commit == self.commit
