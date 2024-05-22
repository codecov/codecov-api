import pytest
from asgiref.sync import async_to_sync
from codecov.commands.exceptions import Unauthorized
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, RepositoryTokenFactory
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from ..update_repository import UpdateRepositoryInteractor


class UpdateRepositoryInteractorTest(TransactionTestCase):
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
