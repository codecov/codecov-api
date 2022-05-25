import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov.commands.exceptions import Unauthenticated
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory

from ..get_graph_token import GetGraphTokenInteractor


class GetGraphTokenInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo_in_org = RepositoryFactory(author=self.org)
        self.random_repo = RepositoryFactory()
        self.user = OwnerFactory(organizations=[self.org.ownerid])

    def execute(self, user, repo):
        current_user = user or AnonymousUser()
        return GetGraphTokenInteractor(current_user, "github").execute(repository=repo)

    async def test_when_unauthenticated_raise(self):
        with pytest.raises(Unauthenticated):
            await self.execute(user="", repo=self.random_repo)

    async def test_get_graph_token_repo_not_in_my_org(self):
        token = await self.execute(user=self.user, repo=self.random_repo)
        assert token is None

    async def test_get_graph_token_repo_in_my_org(self):
        token = await self.execute(user=self.user, repo=self.repo_in_org)
        assert token is self.repo_in_org.image_token
