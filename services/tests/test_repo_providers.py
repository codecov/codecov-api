import inspect
from unittest.mock import patch

import pytest
from django.conf import settings
from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory
from shared.torngit import Bitbucket, Github, Gitlab

from codecov.db import sync_to_async
from codecov_auth.models import (
    GITHUB_APP_INSTALLATION_DEFAULT_NAME,
    GithubAppInstallation,
    Owner,
    Service,
)
from services.repo_providers import RepoProviderService, get_token_refresh_callback
from utils.encryption import encryptor


def mock_get_config_verify_ssl_true(*args):
    if args == ("github", "verify_ssl"):
        return True
    if args == ("github", "ssl_pem"):
        return "ssl_pem"


def mock_get_config_verify_ssl_false(*args):
    if args == ("github", "verify_ssl"):
        return False
    if args == ("github", "ssl_pem"):
        return "ssl_pem"


def mock_get_env_ca_bundle(*args):
    if args == ("REQUESTS_CA_BUNDLE",):
        return "REQUESTS_CA_BUNDLE"


@pytest.mark.parametrize("using_integration", [True, False])
def test__is_using_integration_deprecated_flow(using_integration, db):
    repo = RepositoryFactory.create(using_integration=using_integration)
    assert RepoProviderService()._is_using_integration(None, repo) == using_integration


def test__is_using_integration_ghapp_covers_all_repos(db):
    owner = OwnerFactory.create(service="github")
    repo = RepositoryFactory.create(author=owner)
    other_repo_same_owner = RepositoryFactory.create(author=owner)
    repo_different_owner = RepositoryFactory.create()
    assert repo.author != repo_different_owner.author
    ghapp_installation = GithubAppInstallation(
        name=GITHUB_APP_INSTALLATION_DEFAULT_NAME,
        owner=owner,
        repository_service_ids=None,
        installation_id=12345,
    )
    ghapp_installation.save()
    assert RepoProviderService()._is_using_integration(ghapp_installation, repo) == True
    assert (
        RepoProviderService()._is_using_integration(
            ghapp_installation, other_repo_same_owner
        )
        == True
    )
    assert (
        RepoProviderService()._is_using_integration(
            ghapp_installation, repo_different_owner
        )
        == False
    )


def test__is_using_integration_ghapp_covers_some_repos(db):
    owner = OwnerFactory.create(service="github")
    repo = RepositoryFactory.create(author=owner)
    other_repo_same_owner = RepositoryFactory.create(author=owner)
    repo_different_owner = RepositoryFactory.create()
    assert repo.author != repo_different_owner.author
    ghapp_installation = GithubAppInstallation(
        name=GITHUB_APP_INSTALLATION_DEFAULT_NAME,
        owner=owner,
        repository_service_ids=[repo.service_id],
        installation_id=12345,
    )
    ghapp_installation.save()
    assert RepoProviderService()._is_using_integration(ghapp_installation, repo) == True
    assert (
        RepoProviderService()._is_using_integration(
            ghapp_installation, other_repo_same_owner
        )
        == False
    )
    assert (
        RepoProviderService()._is_using_integration(
            ghapp_installation, repo_different_owner
        )
        == False
    )


@pytest.mark.parametrize(
    "should_have_owner,service",
    [
        (False, Service.GITHUB.value),
        (True, Service.BITBUCKET.value),
        (True, Service.BITBUCKET_SERVER.value),
    ],
)
def test_token_refresh_callback_none_cases(should_have_owner, service, db):
    owner = None
    if should_have_owner:
        owner = OwnerFactory(service=service)
    assert get_token_refresh_callback(owner, service) is None


class TestRepoProviderService(TransactionTestCase):
    def setUp(self):
        self.repo_gh = RepositoryFactory.create(
            author__unencrypted_oauth_token="testaaft3ituvli790m1yajovjv5eg0r4j0264iw",
            author__username="ThiagoCodecov",
            author__service="github",
        )
        self.repo_gl = RepositoryFactory.create(
            author__unencrypted_oauth_token="testaaft3ituvli790m1yajovjv5eg0r4j0264iw",
            author__username="ThiagoCodecov",
            author__service="gitlab",
        )

    @sync_to_async
    def get_owner_gl(self):
        return Owner.objects.filter(ownerid=self.repo_gl.author.ownerid).first()

    @sync_to_async
    def get_owner_gh(self):
        return Owner.objects.filter(ownerid=self.repo_gh.author.ownerid).first()

    def test_get_torngit_with_names_github(self):
        provider = RepoProviderService().get_by_name(
            self.repo_gh.author,
            self.repo_gh.name,
            self.repo_gh.author,
            self.repo_gh.author.service,
        )
        assert isinstance(Github(), type(provider))

    def test_get_torngit_with_names_gitlab(self):
        provider = RepoProviderService().get_by_name(
            self.repo_gl.author,
            self.repo_gl.name,
            self.repo_gl.author,
            self.repo_gl.author.service,
        )
        assert isinstance(provider, Gitlab)
        assert provider._on_token_refresh is not None

    @pytest.mark.asyncio
    async def test_refresh_callback(self):
        provider = RepoProviderService().get_by_name(
            self.repo_gl.author,
            self.repo_gl.name,
            self.repo_gl.author,
            self.repo_gl.author.service,
        )
        assert isinstance(Gitlab(), type(provider))
        assert provider._on_token_refresh is not None
        assert inspect.isawaitable(provider._on_token_refresh())
        owner = await self.get_owner_gl()
        saved_token = encryptor.decrypt_token(owner.oauth_token)
        assert saved_token["key"] == "testaaft3ituvli790m1yajovjv5eg0r4j0264iw"
        assert "refresh_token" not in saved_token

        new_token = {"key": "00001023102301", "refresh_token": "20349230952"}
        await provider._on_token_refresh(new_token)
        owner = await self.get_owner_gl()
        assert owner.username == "ThiagoCodecov"
        saved_token = encryptor.decrypt_token(owner.oauth_token)
        assert saved_token["key"] == "00001023102301"
        assert saved_token["refresh_token"] == "20349230952"

    @pytest.mark.asyncio
    async def test_refresh_callback_github(self):
        provider = RepoProviderService().get_by_name(
            self.repo_gh.author,
            self.repo_gh.name,
            self.repo_gh.author,
            self.repo_gh.author.service,
        )
        assert isinstance(Github(), type(provider))
        assert provider._on_token_refresh is not None
        assert inspect.isawaitable(provider._on_token_refresh())
        owner = await self.get_owner_gh()
        saved_token = encryptor.decrypt_token(owner.oauth_token)
        assert saved_token["key"] == "testaaft3ituvli790m1yajovjv5eg0r4j0264iw"
        assert "refresh_token" not in saved_token

        new_token = {"key": "00001023102301", "refresh_token": "20349230952"}
        await provider._on_token_refresh(new_token)
        owner = await self.get_owner_gh()
        assert owner.username == "ThiagoCodecov"
        saved_token = encryptor.decrypt_token(owner.oauth_token)
        assert saved_token["key"] == "00001023102301"
        assert saved_token["refresh_token"] == "20349230952"

    def test_get_adapter_returns_adapter_for_repo_authors_service(self):
        some_other_user = OwnerFactory(service="github")
        repo = RepositoryFactory.create(
            author__username="ThiagoCodecov", author__service="bitbucket"
        )
        provider = RepoProviderService().get_adapter(some_other_user, repo)
        assert isinstance(Bitbucket(), type(provider))

    def test_get_by_name_returns_adapter_for_repo_owner_service(self):
        some_other_user = OwnerFactory(service="bitbucket")
        repo_name = "gl-repo"
        repo_owner_username = "me"
        repo_owner_service = "gitlab"

        provider = RepoProviderService().get_by_name(
            owner=some_other_user,
            repo_name=repo_name,
            repo_owner_username=repo_owner_username,
            repo_owner_service=repo_owner_service,
        )

        assert isinstance(Gitlab(), type(provider))

    def test_get_by_name_submits_consumer_oauth_token(self):
        user = OwnerFactory(service="bitbucket")
        repo_name = "bb-repo"
        repo_owner_username = "me"
        repo_owner_service = "bitbucket"

        provider = RepoProviderService().get_by_name(
            owner=user,
            repo_name=repo_name,
            repo_owner_username=repo_owner_username,
            repo_owner_service=repo_owner_service,
        )

        assert provider._oauth_consumer_token() is not None

    @patch("services.repo_providers.get_provider")
    @patch("services.repo_providers.get_config")
    def test_get_adapter_verify_ssl_true(self, mock_get_config, mock_get_provider):
        mock_get_config.side_effect = mock_get_config_verify_ssl_true
        bot = OwnerFactory()
        user = OwnerFactory(service="github")
        repo = RepositoryFactory.create(author=user, bot=bot)

        RepoProviderService().get_adapter(
            user, repo, use_ssl=True, token=repo.bot.oauth_token
        )
        mock_get_provider.call_args == (
            (
                "github",
                dict(
                    repo=dict(
                        name=repo.name,
                        using_integration=repo.using_integration,
                        service_id=repo.service_id,
                        private=repo.private,
                    ),
                    owner=dict(username=repo.author.username),
                    token=encryptor.decrypt_token(repo.bot.oauth_token),
                    verify_ssl="ssl_pem",
                    oauth_consumer_token=dict(
                        key=getattr(settings, "GITHUB_CLIENT_ID", "unknown"),
                        secret=getattr(settings, "GITHUB_CLIENT_SECRET", "unknown"),
                    ),
                ),
            ),
        )

    @patch("services.repo_providers.get_provider")
    @patch("services.repo_providers.get_config")
    @patch("services.repo_providers.getenv")
    def test_get_adapter_for_uploads_verify_ssl_false(
        self, mock_get_env, mock_get_config, mock_get_provider
    ):
        mock_get_config.side_effect = mock_get_config_verify_ssl_false
        mock_get_env.side_effect = mock_get_env_ca_bundle
        bot = OwnerFactory()
        user = OwnerFactory(service="github")
        repo = RepositoryFactory.create(author=user, bot=bot)

        RepoProviderService().get_adapter(
            user, repo, use_ssl=True, token=repo.bot.oauth_token
        )
        mock_get_provider.call_args == (
            (
                "github",
                dict(
                    repo=dict(
                        name=repo.name,
                        using_integration=repo.using_integration,
                        service_id=repo.service_id,
                        private=repo.private,
                    ),
                    owner=dict(username=repo.author.username),
                    token=encryptor.decrypt_token(repo.bot.oauth_token),
                    verify_ssl="REQUESTS_CA_BUNDLE",
                    oauth_consumer_token=dict(
                        key=getattr(settings, "GITHUB_CLIENT_ID", "unknown"),
                        secret=getattr(settings, "GITHUB_CLIENT_SECRET", "unknown"),
                    ),
                ),
            ),
        )

    def test_get_adapter_sets_token_to_bot_when_user_not_authenticated(self):
        repo_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(author=repo_owner)
        adapter = RepoProviderService().get_adapter(None, repo)
        assert adapter.token["key"] == settings.GITHUB_BOT_KEY

    def test_get_by_name_sets_token_to_bot_when_user_not_authenticated(self):
        repo_name = "gh-repo"
        repo_owner_username = "me"
        repo_owner_service = "github"

        adapter = RepoProviderService().get_by_name(
            owner=None,
            repo_name=repo_name,
            repo_owner_username=repo_owner_username,
            repo_owner_service=repo_owner_service,
        )

        assert adapter.token["key"] == settings.GITHUB_BOT_KEY

    def test_get_adapter_sets_owner_service_id(self):
        owner = OwnerFactory()
        repo = RepositoryFactory(author=owner)
        user = OwnerFactory()
        adapter = RepoProviderService().get_adapter(owner=user, repo=repo)
        assert adapter.data["owner"]["service_id"] == owner.service_id

    @pytest.mark.asyncio
    @patch(
        "services.repo_providers.RepoProviderService._get_adapter",
        return_value="torngit_adapter",
    )
    async def test_async_get_adapter(self, mock__get_adapter):
        owner = await self.get_owner_gh()
        ghapp_installation = GithubAppInstallation(
            name=GITHUB_APP_INSTALLATION_DEFAULT_NAME,
            installation_id=1234,
            owner=owner,
            repository_service_ids=None,
        )
        await ghapp_installation.asave()
        fetched = await RepoProviderService().async_get_adapter(owner, self.repo_gh)
        assert fetched == "torngit_adapter"
        mock__get_adapter.assert_called_with(
            owner, self.repo_gh, ghapp=ghapp_installation
        )

    @pytest.mark.asyncio
    @patch(
        "services.repo_providers.RepoProviderService._get_adapter",
        return_value="torngit_adapter",
    )
    async def test_async_get_adapter_owner_not_github(self, mock__get_adapter):
        owner = await self.get_owner_gl()
        fetched = await RepoProviderService().async_get_adapter(owner, self.repo_gl)
        assert fetched == "torngit_adapter"
        mock__get_adapter.assert_called_with(owner, self.repo_gl, ghapp=None)

    @pytest.mark.asyncio
    @patch(
        "services.repo_providers.RepoProviderService._get_adapter",
        return_value="torngit_adapter",
    )
    async def test_async_get_adapter_no_installation(self, mock__get_adapter):
        owner = await self.get_owner_gh()
        fetched = await RepoProviderService().async_get_adapter(owner, self.repo_gh)
        assert fetched == "torngit_adapter"
        mock__get_adapter.assert_called_with(owner, self.repo_gh, ghapp=None)
