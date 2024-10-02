import pytest
from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import (
    OwnerFactory,
    RepositoryFactory,
    RepositoryTokenFactory,
)

from codecov.commands.exceptions import Unauthenticated

from ..get_repository_token import GetRepositoryTokenInteractor


class GetRepositoryTokenInteractorTest(TransactionTestCase):
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

    def execute(self, owner, repo, token_type="profiling"):
        return GetRepositoryTokenInteractor(owner, "github").execute(
            repository=repo, token_type=token_type
        )

    async def test_when_unauthenticated_raise(self):
        with pytest.raises(Unauthenticated):
            await self.execute(owner="", repo=self.active_repo)

    async def test_when_repo_inactive(self):
        token = await self.execute(owner=self.user, repo=self.inactive_repo)
        assert token is None

    async def test_when_repo_has_no_token(self):
        token = await self.execute(owner=self.user, repo=self.repo_with_no_token)
        assert token is not None
        assert len(token) == 40

    async def test_get_profiling_token(self):
        token = await self.execute(owner=self.user, repo=self.active_repo)
        assert token is not None
        assert token == "random"

    async def test_get_static_analysis_token(self):
        token = await self.execute(
            owner=self.user, repo=self.active_repo, token_type="static_analysis"
        )
        assert token is not None
        assert len(token) == 40
