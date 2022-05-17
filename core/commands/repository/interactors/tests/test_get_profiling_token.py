import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov.commands.exceptions import Unauthenticated
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, RepositoryTokenFactory

from ..get_profiling_token import GetProfilingTokenInteractor


class GetProfilingTokenInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory(name="codecov")
        self.repo = RepositoryFactory(author=self.org, name="gazebo")
        self.user = OwnerFactory(organizations=[self.org.ownerid])
        RepositoryTokenFactory(repository=self.repo, key="random")

    def execute(self, user):
        current_user = user or AnonymousUser()
        return GetProfilingTokenInteractor(current_user, "github").execute(
            repository=self.repo
        )

    async def test_when_unauthenticated_raise(self):
        with pytest.raises(Unauthenticated):
            await self.execute(user="")

    async def test_get_profiling_token(self):
        token = await self.execute(user=self.user)
        assert token is not None
        assert token == "random"
