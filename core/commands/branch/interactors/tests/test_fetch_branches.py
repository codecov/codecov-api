import pytest
from asgiref.sync import async_to_sync
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
            BranchFactory(repository=self.repo, head=self.head.commitid),
            BranchFactory(repository=self.repo, head=self.head.commitid),
        ]

    def execute(self, user, *args):
        service = user.service if user else "github"
        current_user = user
        return FetchRepoBranchesInteractor(current_user, service).execute(*args)

    def test_fetch_branches(self):
        repository = self.repo
        branches = async_to_sync(self.execute)(None, repository)
        assert any(branch.name == "master" for branch in branches)
        assert len(branches) == 3  # counting master too

