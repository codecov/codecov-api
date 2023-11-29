import pytest
from django.test import TransactionTestCase

from codecov.commands.exceptions import ValidationError
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from graphql_api.types.enums.enums import CiProvider

from ..config_repo_via_PR import ConfigureRepoViaPRInteractor


class TestConfigRepoViaPRInteractor(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov")
        self.new_repo = RepositoryFactory(
            author=self.org, name="new-repo", active=False
        )
        self.user = OwnerFactory(
            organizations=[self.org.ownerid],
            permission=[self.new_repo.repoid],
        )
        self.random_user = OwnerFactory(organizations=[self.org.ownerid])

    def execute(self, owner, repo, provider):
        return ConfigureRepoViaPRInteractor(owner, "github").execute(
            repo_name=repo.name,
            owner_username=self.org.username,
            ci_provider=provider,
        )

    async def test_when_validation_error_ci_provider_not_supported(self):
        missing_provider = "CIRCLECI"
        with pytest.raises(ValidationError) as exp:
            await self.execute(
                owner=self.user, repo=self.new_repo, provider=missing_provider
            )
        assert str(exp.value) == f"Provider {missing_provider} is not supported"

    async def test_when_validation_error_repo_not_found(self):
        with pytest.raises(ValidationError):
            await ConfigureRepoViaPRInteractor(self.random_user, "github").execute(
                repo_name="missing-repo",
                owner_username=self.org.username,
                ci_provider=CiProvider.GITHUB_ACTIONS,
            )

    async def test_validation_ok(self):
        result = await self.execute(
            owner=self.user, repo=self.new_repo, provider=CiProvider.GITHUB_ACTIONS
        )
        assert result is False
