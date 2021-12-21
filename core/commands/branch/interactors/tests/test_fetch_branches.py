import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import BranchFactory, CommitFactory, RepositoryFactory

from ..fetch_branches import FetchRepoBranchesInteractor


class FetchRepoBranchesInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov")
        self.repo = RepositoryFactory(author=self.org, name="gazebo", private=False)
        self.head = CommitFactory(repository=self.repo)
        self.commit = CommitFactory(repository=self.repo)
        self.branches = [
            BranchFactory(repository=self.repo, head=self.commit.commitid),
            BranchFactory(repository=self.repo, head=self.head.commitid),
        ]

    # helper to execute the interactor
    def execute(self, user, *args):
        service = user.service if user else "github"
        current_user = user or AnonymousUser()
        return FetchRepoBranchesInteractor(current_user, service).execute(*args)

    @sync_to_async
    def test_fetch_branches(self):
        branches = self.execute(self.repo)
        assert list(branches) == self.branches
