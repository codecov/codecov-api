from xml.dom import ValidationErr

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov.commands.exceptions import Unauthenticated, ValidationError
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, RepositoryTokenFactory

from ..get_profiling_token import GetProfilingTokenInteractor


class GetProfilingTokenInteractorTest(TransactionTestCase):
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
        self.user = OwnerFactory(organizations=[self.org.ownerid])
        RepositoryTokenFactory(repository=self.active_repo, key="random")

    def execute(self, user, repo):
        current_user = user or AnonymousUser()
        return GetProfilingTokenInteractor(current_user, "github").execute(
            repository=repo
        )

    async def test_when_unauthenticated_raise(self):
        with pytest.raises(Unauthenticated):
            await self.execute(user="", repo=self.active_repo)

    async def test_when_repo_inactive(self):
        with pytest.raises(ValidationError):
            await self.execute(user=self.user, repo=self.inactive_repo)

    async def test_when_repo_has_no_token(self):
        token = await self.execute(user=self.user, repo=self.repo_with_no_token)
        assert token is not None
        assert len(token) == 40

    async def test_get_profiling_token(self):
        token = await self.execute(user=self.user, repo=self.active_repo)
        assert token is not None
        assert token == "random"
