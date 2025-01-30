import pytest
from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from codecov.commands.exceptions import Unauthorized

from ..erase_repository import EraseRepositoryInteractor


class UpdateRepositoryInteractorTest(TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov")
        self.random_user = OwnerFactory(organizations=[])
        self.non_admin_user = OwnerFactory(organizations=[self.owner.ownerid])

    def execute_unauthorized_owner(self):
        return EraseRepositoryInteractor(self.owner, "github").execute(
            self.random_user.username, "repo-1"
        )

    def execute_user_not_admin(self):
        return EraseRepositoryInteractor(self.non_admin_user, "github").execute(
            self.owner.username, "repo-1"
        )

    async def test_when_validation_error_unauthorized_owner_not_part_of_org(self):
        with pytest.raises(Unauthorized):
            await self.execute_unauthorized_owner()

    async def test_when_validation_error_unauthorized_owner_not_admin(self):
        with pytest.raises(Unauthorized):
            await self.execute_user_not_admin()
