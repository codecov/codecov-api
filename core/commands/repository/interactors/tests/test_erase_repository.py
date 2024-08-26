import pytest
from django.test import TransactionTestCase

from codecov.commands.exceptions import Unauthorized
from codecov_auth.tests.factories import OwnerFactory

from ..erase_repository import EraseRepositoryInteractor


class UpdateRepositoryInteractorTest(TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov")
        self.random_user = OwnerFactory(organizations=[])
        self.non_admin_user = OwnerFactory(organizations=[self.owner.ownerid])

    def execute_unauthorized_owner(self):
        return EraseRepositoryInteractor(self.owner, "github").execute(
            repo_name="repo-1",
            owner=self.random_user,
        )

    def execute_user_not_admin(self):
        return EraseRepositoryInteractor(self.non_admin_user, "github").execute(
            repo_name="repo-1",
            owner=self.owner,
        )

    async def test_when_validation_error_unauthorized_owner_not_part_of_org(self):
        with pytest.raises(Unauthorized):
            await self.execute_unauthorized_owner()

    async def test_when_validation_error_unauthorized_owner_not_admin(self):
        with pytest.raises(Unauthorized):
            await self.execute_user_not_admin()
