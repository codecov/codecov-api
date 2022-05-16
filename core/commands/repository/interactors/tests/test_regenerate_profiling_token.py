import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase
from asgiref.sync import async_to_sync

from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, RepositoryTokenFactory
from ..regenerate_profiling_token import RegenerateProfilingTokenInteractor


class RegenerateProfilingTokenInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory(name="codecov")
        self.repo = RepositoryFactory(author=self.org, name="gazebo")
        RepositoryTokenFactory(repository=self.repo, key='random')
        self.user = OwnerFactory(organizations=[self.org.ownerid], permission=[self.repo.repoid])
        self.random_user = OwnerFactory(organizations=[self.org.ownerid])

    def execute(self, user):
        current_user = user or AnonymousUser()
        return RegenerateProfilingTokenInteractor(current_user, "github").execute(repoName=self.repo.name, owner=self.org.name)

    async def test_when_unauthenticated_raise(self):
        with pytest.raises(Unauthenticated):
            await self.execute(user="")

    async def test_when_validation_error_repo_not_viewable(self):
        with pytest.raises(ValidationError):
            await self.execute(user=self.random_user)

    async def test_regenerate_profiling_token(self):
        token = await self.execute(user=self.user)
        assert token is not None
        assert token is not "random"
        assert len(token) == 40

