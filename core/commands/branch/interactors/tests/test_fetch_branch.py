from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import BranchFactory, OwnerFactory

from ..fetch_branch import FetchBranchInteractor


class FetchBranchInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory()
        self.branch = BranchFactory()
        self.repo = self.branch.repository

    # helper to execute the interactor
    def execute(self, owner, *args):
        service = owner.service if owner else "github"
        return FetchBranchInteractor(owner, service).execute(*args)

    async def test_fetch_branch(self):
        branch = await self.execute(None, self.repo, self.branch.name)
        assert branch == self.branch

    async def test_fetch_branch_doesnt_exist(self):
        branch = await self.execute(None, self.repo, "do not exist")
        assert branch is None
