import pytest
from django.test import TestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from codecov.commands.exceptions import Unauthorized

from ..update_repository import UpdateRepositoryInteractor


class UpdateRepositoryInteractorTest(TestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov")
        self.random_user = OwnerFactory(organizations=[])

    def execute_unauthorized_owner(self):
        return UpdateRepositoryInteractor(self.owner, "github").execute(
            repo_name="repo-1",
            owner=self.random_user,
            default_branch=None,
            activated=None,
        )

    async def test_when_validation_error_unauthorized_owner(self):
        with pytest.raises(Unauthorized):
            await self.execute_unauthorized_owner()
