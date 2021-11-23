import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import BranchFactory

from ..fetch_branch import FetchBranchInteractor


class FetchBranchInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory()
        self.branch = BranchFactory()
        self.repo = self.branch.repository

    # helper to execute the interactor
    def execute(self, user, *args):
        service = user.service if user else "github"
        current_user = user or AnonymousUser()
        return FetchBranchInteractor(current_user, service).execute(*args)

    async def test_fetch_branch(self):
        branch = await self.execute(None, self.repo, self.branch.name)
        assert branch == self.branch

    async def test_fetch_branch_doesnt_exist(self):
        branch = await self.execute(None, self.repo, "do not exist")
        assert branch is None
