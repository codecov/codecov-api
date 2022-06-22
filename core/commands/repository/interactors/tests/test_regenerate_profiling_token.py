import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, RepositoryTokenFactory

from ..regenerate_profiling_token import RegenerateProfilingTokenInteractor


class RegenerateProfilingTokenInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory(name="codecov")
        self.active_repo = RepositoryFactory(
            author=self.org, name="gazebo", active=True
        )
        self.inactive_repo = RepositoryFactory(
            author=self.org, name="backend", active=False
        )
        self.repo_with_no_token = RepositoryFactory(
            author=self.org, name="frontend", active=True
        )
        RepositoryTokenFactory(repository=self.active_repo, key="random")
        self.user = OwnerFactory(
            organizations=[self.org.ownerid],
            permission=[self.active_repo.repoid, self.repo_with_no_token.repoid],
        )
        self.random_user = OwnerFactory(organizations=[self.org.ownerid])

    def execute(self, user, repo):
        current_user = user or AnonymousUser()
        return RegenerateProfilingTokenInteractor(current_user, "github").execute(
            repo_name=repo.name, owner=self.org.name
        )

    async def test_when_unauthenticated_raise(self):
        with pytest.raises(Unauthenticated):
            await self.execute(user="", repo=self.active_repo)

    async def test_when_validation_error_repo_not_active(self):
        with pytest.raises(ValidationError):
            await self.execute(user=self.random_user, repo=self.inactive_repo)

    async def test_when_validation_error_repo_not_viewable(self):
        with pytest.raises(ValidationError):
            await self.execute(user=self.random_user, repo=self.active_repo)

    async def test_regenerate_profiling_token_repo_has_no_token(self):
        token = await self.execute(user=self.user, repo=self.repo_with_no_token)
        assert token is not None
        assert len(token) == 40

    async def test_regenerate_profiling_token(self):
        token = await self.execute(user=self.user, repo=self.active_repo)
        assert token is not None
        assert token is not "random"
        assert len(token) == 40
