from unittest.mock import patch

from django.test import TestCase
from shared.torngit.exceptions import TorngitClientError, TorngitClientGeneralError

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from internal_api.repo.repository_accessors import RepoAccessors


class RepositoryAccessorsTestCase(TestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov", service="github")

        self.repo1 = RepositoryFactory(
            author=self.org, active=True, private=True, name="A"
        )
        self.repo2 = RepositoryFactory(
            author=self.org, active=True, private=True, name="B"
        )

        self.user = OwnerFactory(
            username="codecov-user", service="github", organizations=[self.org.ownerid],
        )

        self.client.force_login(user=self.user)

    def test_get_repo_permissions_when_author(self):
        user = OwnerFactory(username="myself", service="github")
        repo = RepositoryFactory(author=user, active=True, private=True, name="A")
        can_view, can_edit = RepoAccessors().get_repo_permissions(user, repo)
        assert (can_view, can_edit) == (True, True)

    def test_get_repo_details_if_exists(self):
        repo = RepoAccessors.get_repo_details(
            self, self.user, self.repo1.name, self.org.username, self.org.service
        )
        self.assertEqual(repo, self.repo1)

    def test_get_repo_details_if_not_exists(self):
        repo = RepoAccessors.get_repo_details(
            self, self.user, "repo-not-in-db", self.org.username, self.org.service
        )
        self.assertEqual(repo, None)

    @patch("services.repo_providers.RepoProviderService.get_by_name")
    def test_fetch_and_create_repo(self, mocked_repo_provider_service):
        git_repo_response = {
            "repo": {
                "name": "new-repo",
                "branch": "default",
                "private": True,
                "service_id": "123",
                "fork": {
                    "repo": {
                        "name": "fork-repo",
                        "branch": "master",
                        "private": True,
                        "service_id": "678",
                    },
                    "owner": {"username": "fork_owner", "service_id": "234"},
                },
            },
            "owner": {"username": "new-org", "service_id": "456"},
        }

        class MockedRepoService:
            async def get_repository(self):
                return git_repo_response

        mocked_repo_provider_service.return_value = MockedRepoService()

        repo = RepoAccessors.fetch_from_git_and_create_repo(
            self, self.user, "new-repo", "new-org", "github"
        )
        assert repo.name == git_repo_response["repo"]["name"]
        assert repo.fork is not None

    @patch("services.repo_providers.RepoProviderService")
    def test_fetch_and_create_repo_if_torngit_error(self, mocked_repo_provider_service):
        class MockedRepoService:
            async def get_repository(self):
                raise TorngitClientGeneralError(404, response=None, message="Not Found")

        mocked_repo_provider_service.return_value = MockedRepoService()

        with self.assertRaises(TorngitClientError):
            RepoAccessors.fetch_from_git_and_create_repo(
                self, self.user, "repo-not-in-db", self.org.username, self.org.service
            )
