import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov.commands.exceptions import (
    NotFound,
    Unauthenticated,
    Unauthorized,
    ValidationError,
)
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory

from ..fetch_repository import FetchRepositoryInteractor


class FetchRepositoryInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory()
        self.public_repo = RepositoryFactory(author=self.org, private=False)
        self.hidden_private_repo = RepositoryFactory(author=self.org, private=True)
        self.private_repo = RepositoryFactory(author=self.org, private=True)
        self.current_user = OwnerFactory(
            permission=[self.private_repo.repoid], organizations=[self.org.ownerid]
        )

    # helper to execute the interactor
    def execute(self, user, *args):
        service = user.service if user else "github"
        current_user = user or AnonymousUser()
        return FetchRepositoryInteractor(current_user, service).execute(*args)

    async def test_fetch_public_repo_unauthenticated(self):
        repo = await self.execute(None, self.org, self.public_repo.name)
        assert repo == self.public_repo

    async def test_fetch_public_repo_authenticated(self):
        repo = await self.execute(self.current_user, self.org, self.public_repo.name)
        assert repo == self.public_repo

    async def test_fetch_private_repo_unauthenticated(self):
        repo = await self.execute(None, self.org, self.private_repo.name)
        assert repo is None

    async def test_fetch_private_repo_authenticated_but_no_permissions(self):
        repo = await self.execute(
            self.current_user, self.org, self.hidden_private_repo.name
        )
        assert repo is None

    async def test_fetch_private_repo_authenticated_with_permissions(self):
        repo = await self.execute(self.current_user, self.org, self.private_repo.name)
        assert repo == self.private_repo
