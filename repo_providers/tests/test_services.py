from torngit import Github

from codecov.tests.base_test import InternalAPITest
from core.tests.factories import RepositoryFactory
from repo_providers.services import TorngitInitializationFailed, RepoProviderService


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
        provider = RepoProviderService().get_by_name(repo.author, repo.name, repo.author.username)
        assert isinstance(Github(), type(provider))
