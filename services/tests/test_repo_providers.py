import inspect
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from shared.torngit import Bitbucket, Github, Gitlab

from codecov.db import sync_to_async
from codecov.tests.base_test import InternalAPITest
from codecov_auth.models import Owner
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from services.repo_providers import RepoProviderService
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


class TestRepoProviderService(InternalAPITest):
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

    def test_get_torngit_with_names(self):
        provider = RepoProviderService().get_by_name(
            self.repo_gh.author,
            self.repo_gh.name,
            self.repo_gh.author,
            self.repo_gh.author.service,
        )
        assert isinstance(Github(), type(provider))

    def test_get_torngit_with_names(self):
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
            user=some_other_user,
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
            user=user,
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

        provider = RepoProviderService().get_adapter(
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
                        key=getattr(settings, f"GITHUB_CLIENT_ID", "unknown"),
                        secret=getattr(settings, f"GITHUB_CLIENT_SECRET", "unknown"),
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

        provider = RepoProviderService().get_adapter(
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
                        key=getattr(settings, f"GITHUB_CLIENT_ID", "unknown"),
                        secret=getattr(settings, f"GITHUB_CLIENT_SECRET", "unknown"),
                    ),
                ),
            ),
        )

    def test_get_adapter_sets_token_to_bot_when_user_not_authenticated(self):
        user = AnonymousUser()
        repo_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(author=repo_owner)
        adapter = RepoProviderService().get_adapter(user, repo)
        assert adapter.token["key"] == settings.GITHUB_BOT_KEY

    def test_get_by_name_sets_token_to_bot_when_user_not_authenticated(self):
        user = AnonymousUser()
        repo_name = "gh-repo"
        repo_owner_username = "me"
        repo_owner_service = "github"

        adapter = RepoProviderService().get_by_name(
            user=user,
            repo_name=repo_name,
            repo_owner_username=repo_owner_username,
            repo_owner_service=repo_owner_service,
        )

        assert adapter.token["key"] == settings.GITHUB_BOT_KEY

    def test_get_adapter_sets_owner_service_id(self):
        owner = OwnerFactory()
        repo = RepositoryFactory(author=owner)
        user = OwnerFactory()
        adapter = RepoProviderService().get_adapter(user=user, repo=repo)
        assert adapter.data["owner"]["service_id"] == owner.service_id
