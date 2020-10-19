from shared.torngit import Github, Bitbucket, Gitlab

from codecov.tests.base_test import InternalAPITest
from core.tests.factories import RepositoryFactory
from codecov_auth.tests.factories import OwnerFactory
from services.repo_providers import TorngitInitializationFailed, RepoProviderService
from django.contrib.auth.models import AnonymousUser
from django.conf import settings


class TestRepoProviderService(InternalAPITest):

    def test_failed_torngit_initialization(self):
        repo = RepositoryFactory.create(
            author__unencrypted_oauth_token='testaaft3ituvli790m1yajovjv5eg0r4j0264iw',
            author__username='ThiagoCodecov',
            author__service='unknown'
        )
        with self.assertRaises(TorngitInitializationFailed):
            RepoProviderService().get_adapter(repo.author, repo)

    def test_get_torngit_with_names(self):
        repo = RepositoryFactory.create(
            author__unencrypted_oauth_token='testaaft3ituvli790m1yajovjv5eg0r4j0264iw',
            author__username='ThiagoCodecov',
            author__service='github'
        )
        provider = RepoProviderService().get_by_name(repo.author, repo.name, repo.author, repo.author.service)
        assert isinstance(Github(), type(provider))

    def test_get_adapter_returns_adapter_for_repo_authors_service(self):
        some_other_user = OwnerFactory(service='github')
        repo = RepositoryFactory.create(
            author__username='ThiagoCodecov',
            author__service='bitbucket'
        )
        provider = RepoProviderService().get_adapter(some_other_user, repo)
        assert isinstance(Bitbucket(), type(provider))

    def test_get_by_name_returns_adapter_for_repo_owner_service(self):
        some_other_user = OwnerFactory(service='bitbucket')
        repo_name = 'gl-repo'
        repo_owner_username = 'me'
        repo_owner_service = 'gitlab'

        provider = RepoProviderService().get_by_name(
            user=some_other_user,
            repo_name=repo_name,
            repo_owner_username=repo_owner_username,
            repo_owner_service=repo_owner_service
        )

        assert isinstance(Gitlab(), type(provider))

    def test_get_by_name_submits_consumer_oauth_token(self):
        user = OwnerFactory(service='bitbucket')
        repo_name = 'bb-repo'
        repo_owner_username = 'me'
        repo_owner_service = 'bitbucket'

        provider = RepoProviderService().get_by_name(
            user=user,
            repo_name=repo_name,
            repo_owner_username=repo_owner_username,
            repo_owner_service=repo_owner_service
        )

        assert provider._oauth_consumer_token() is not None

    def test_get_adapter_sets_token_to_bot_when_user_not_authenticated(self):
        user = AnonymousUser()
        repo_owner = OwnerFactory(service="github")
        repo = RepositoryFactory(author=repo_owner)
        adapter = RepoProviderService().get_adapter(user, repo)
        assert adapter.token["key"] == settings.GITHUB_CLIENT_BOT

    def test_get_by_name_sets_token_to_bot_when_user_not_authenticated(self):
        user = AnonymousUser()
        repo_name = 'gh-repo'
        repo_owner_username = 'me'
        repo_owner_service = 'github'

        adapter = RepoProviderService().get_by_name(
            user=user,
            repo_name=repo_name,
            repo_owner_username=repo_owner_username,
            repo_owner_service=repo_owner_service
        )

        assert adapter.token["key"] == settings.GITHUB_CLIENT_BOT
