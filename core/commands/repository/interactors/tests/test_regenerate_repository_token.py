import pytest
from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import (
    OwnerFactory,
    RepositoryFactory,
    RepositoryTokenFactory,
)

from codecov.commands.exceptions import ValidationError

from ..regenerate_repository_token import RegenerateRepositoryTokenInteractor


class RegenerateRepositoryTokenInteractorTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov")
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

    def execute(self, owner, repo):
        return RegenerateRepositoryTokenInteractor(owner, "github").execute(
            repo_name=repo.name,
            owner_username=self.org.username,
            token_type="upload",
        )

    async def test_when_validation_error_repo_not_active(self):
        with pytest.raises(ValidationError):
            await self.execute(owner=self.random_user, repo=self.inactive_repo)

    async def test_when_validation_error_repo_not_viewable(self):
        with pytest.raises(ValidationError):
            await self.execute(owner=self.random_user, repo=self.active_repo)
