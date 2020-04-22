from django.test import TestCase

from unittest.mock import patch

from core.tests.factories import RepositoryFactory
from codecov_auth.tests.factories import OwnerFactory

from internal_api.permissions import RepositoryPermissionsService


class MockedPermissionsAdapter:
    async def get_authenticated(self):
        return True, True


class TestRepositoryPermissionsService(TestCase):
    def setUp(self):
        self.permissions_service = RepositoryPermissionsService()

    def test_has_read_permissions_returns_true_if_user_is_owner(self):
        owner = OwnerFactory()
        repo = RepositoryFactory(author=owner)
        assert self.permissions_service.has_read_permissions(owner, repo) is True

    def test_has_read_permissions_returns_true_if_repoid_in_permission_array(self):
        repo = RepositoryFactory(author=OwnerFactory())
        owner = OwnerFactory(permission=[repo.repoid])
        assert self.permissions_service.has_read_permissions(owner, repo) is True

    def test_has_read_permissions_returns_true_if_repo_not_private(self):
        repo = RepositoryFactory(private=False)
        owner = OwnerFactory()
        assert self.permissions_service.has_read_permissions(owner, repo) is True

    @patch('internal_api.permissions.RepositoryPermissionsService._fetch_provider_permissions')
    def test_has_read_permissions_gets_permissions_from_provider_if_above_conds_not_met(
        self,
        fetch_mock
    ):
        fetch_mock.return_value = True, False
        repo = RepositoryFactory()
        owner = OwnerFactory()

        assert self.permissions_service.has_read_permissions(owner, repo) is True

        fetch_mock.assert_called_once_with(owner, repo)

    @patch('services.repo_providers.RepoProviderService.get_adapter')
    def test_fetch_provider_permissions_fetches_permissions_from_provider(
        self,
        mocked_provider
    ):
        mocked_provider.return_value = MockedPermissionsAdapter()
        repo = RepositoryFactory()
        owner = OwnerFactory()

        assert self.permissions_service._fetch_provider_permissions(owner, repo) == (True, True)

    @patch('services.repo_providers.RepoProviderService.get_adapter')
    def test_fetch_provider_permissions_caches_read_permissions(
        self,
        mocked_provider
    ):
        mocked_provider.return_value = MockedPermissionsAdapter()
        repo = RepositoryFactory()
        owner = OwnerFactory()
        self.permissions_service._fetch_provider_permissions(owner, repo)

        owner.refresh_from_db()
        assert repo.repoid in owner.permission
