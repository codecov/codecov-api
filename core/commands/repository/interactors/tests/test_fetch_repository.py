from django.test import TransactionTestCase
from shared.django_apps.codecov_auth.tests.factories import (
    AccountFactory,
    OktaSettingsFactory,
)
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory

from ..fetch_repository import FetchRepositoryInteractor


class FetchRepositoryInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory()

        self.okta_account = AccountFactory()
        self.okta_settings = OktaSettingsFactory(
            account=self.okta_account, enforced=True
        )
        self.okta_org = OwnerFactory(account=self.okta_account)

        self.public_repo = RepositoryFactory(author=self.org, private=False)
        self.hidden_private_repo = RepositoryFactory(author=self.org, private=True)
        self.private_repo = RepositoryFactory(author=self.org, private=True)
        self.okta_private_repo = RepositoryFactory(author=self.okta_org, private=True)
        self.current_user = OwnerFactory(
            permission=[self.private_repo.repoid, self.okta_private_repo.repoid],
            organizations=[self.org.ownerid, self.okta_org.ownerid],
        )

    # helper to execute the interactor
    def execute(self, owner, *args, **kwargs):
        service = owner.service if owner else "github"
        return FetchRepositoryInteractor(owner, service).execute(*args, **kwargs)

    async def test_fetch_public_repo_unauthenticated(self):
        repo = await self.execute(None, self.org, self.public_repo.name, [])
        assert repo == self.public_repo

    async def test_fetch_public_repo_authenticated(self):
        repo = await self.execute(
            self.current_user, self.org, self.public_repo.name, []
        )
        assert repo == self.public_repo

    async def test_fetch_private_repo_unauthenticated(self):
        repo = await self.execute(None, self.org, self.private_repo.name, [])
        assert repo is None

    async def test_fetch_private_repo_authenticated_but_no_permissions(self):
        repo = await self.execute(
            self.current_user, self.org, self.hidden_private_repo.name, []
        )
        assert repo is None

    async def test_fetch_private_repo_authenticated_with_permissions(self):
        repo = await self.execute(
            self.current_user, self.org, self.private_repo.name, []
        )
        assert repo == self.private_repo

    async def test_fetch_okta_private_repo_authenticated(self):
        repo = await self.execute(
            self.current_user,
            self.okta_org,
            self.okta_private_repo.name,
            [self.okta_account.id],
        )
        assert repo == self.okta_private_repo

    async def test_fetch_okta_private_repo_unauthenticated(self):
        repo = await self.execute(
            self.current_user,
            self.okta_org,
            self.okta_private_repo.name,
            [],
        )
        assert repo is None

    async def test_fetch_okta_private_repo_do_not_exclude_unauthenticated(self):
        repo = await self.execute(
            self.current_user,
            self.okta_org,
            self.okta_private_repo.name,
            [],
            exclude_okta_enforced_repos=False,
        )
        assert repo == self.okta_private_repo
