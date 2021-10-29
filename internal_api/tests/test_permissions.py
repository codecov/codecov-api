from unittest.mock import patch

from django.test import TestCase
from rest_framework.exceptions import APIException
from rest_framework.test import APIRequestFactory

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from internal_api.permissions import (
    RepositoryPermissionsService,
    UserIsAdminPermissions,
)
from internal_api.tests.test_utils import (
    GetAdminErrorProviderAdapter,
    GetAdminProviderAdapter,
)


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

    @patch(
        "internal_api.permissions.RepositoryPermissionsService._fetch_provider_permissions"
    )
    def test_has_read_permissions_gets_permissions_from_provider_if_above_conds_not_met(
        self, fetch_mock
    ):
        fetch_mock.return_value = True, False
        repo = RepositoryFactory()
        owner = OwnerFactory()

        assert self.permissions_service.has_read_permissions(owner, repo) is True

        fetch_mock.assert_called_once_with(owner, repo)

    @patch("services.repo_providers.RepoProviderService.get_adapter")
    def test_fetch_provider_permissions_fetches_permissions_from_provider(
        self, mocked_provider
    ):
        mocked_provider.return_value = MockedPermissionsAdapter()
        repo = RepositoryFactory()
        owner = OwnerFactory()

        assert self.permissions_service._fetch_provider_permissions(owner, repo) == (
            True,
            True,
        )

    @patch("services.repo_providers.RepoProviderService.get_adapter")
    def test_fetch_provider_permissions_caches_read_permissions(self, mocked_provider):
        mocked_provider.return_value = MockedPermissionsAdapter()
        repo = RepositoryFactory()
        owner = OwnerFactory()
        self.permissions_service._fetch_provider_permissions(owner, repo)

        owner.refresh_from_db()
        assert repo.repoid in owner.permission

    @patch("services.repo_providers.RepoProviderService.get_adapter")
    def test_fetch_provider_permissions_caches_read_permissions_when_owner_has_no_permissions(
        self, mocked_provider
    ):
        mocked_provider.return_value = MockedPermissionsAdapter()
        repo = RepositoryFactory()
        owner = OwnerFactory(permission=None)
        self.permissions_service._fetch_provider_permissions(owner, repo)

        owner.refresh_from_db()
        assert repo.repoid in owner.permission

    def test_user_is_activated_returns_false_if_user_not_in_owner_org(self):
        with self.subTest("user orgs is None"):
            user = OwnerFactory()
            owner = OwnerFactory(plan="users-inappy")
            assert self.permissions_service.user_is_activated(user, owner) is False

        with self.subTest("owner not in user orgs"):
            owner = OwnerFactory(plan="users-inappy")
            user = OwnerFactory(organizations=[])
            assert self.permissions_service.user_is_activated(user, owner) is False

    def test_user_is_activated_returns_true_when_owner_has_legacy_plan(self):
        user = OwnerFactory()
        owner = OwnerFactory(plan="v4-50m")
        assert self.permissions_service.user_is_activated(user, owner) is True

    def test_user_is_activated_returns_true_when_user_is_owner(self):
        user = OwnerFactory()
        assert self.permissions_service.user_is_activated(user, user) is True

    def test_user_is_activated_returns_true_if_user_is_activated(self):
        user = OwnerFactory()
        owner = OwnerFactory(plan="users-inappy", plan_activated_users=[user.ownerid])
        user.organizations = [owner.ownerid]
        user.save()

        assert self.permissions_service.user_is_activated(user, owner) is True

    def test_user_is_activated_activates_user_and_returns_true_if_can_auto_activate(
        self,
    ):
        user = OwnerFactory()
        owner = OwnerFactory(
            plan="users-inappy", plan_auto_activate=True, plan_user_count=1
        )
        user.organizations = [owner.ownerid]
        user.save()

        assert self.permissions_service.user_is_activated(user, owner) is True

        owner.refresh_from_db()
        assert user.ownerid in owner.plan_activated_users

    @patch("services.segment.SegmentService.account_activated_user")
    def test_user_auto_activation_triggers_segment_event(
        self, segment_activate_user_mock
    ):
        user = OwnerFactory()
        owner = OwnerFactory(
            plan="users-inappy", plan_auto_activate=True, plan_user_count=1
        )
        user.organizations = [owner.ownerid]
        user.save()

        self.permissions_service.user_is_activated(user, owner)
        segment_activate_user_mock.assert_called_once_with(
            current_user_ownerid=user.ownerid,
            ownerid_to_activate=user.ownerid,
            org_ownerid=owner.ownerid,
            auto_activated=True,
        )

    def test_user_is_activated_returns_false_if_cant_auto_activate(self):
        owner = OwnerFactory(plan="users-inappy", plan_user_count=10)
        user = OwnerFactory(organizations=[owner.ownerid])

        with self.subTest("auto activate set to false"):
            owner.plan_auto_activate = False
            owner.save()
            assert self.permissions_service.user_is_activated(user, owner) is False

        with self.subTest("auto activate true but not enough seats"):
            owner.plan_auto_activate = True
            owner.plan_user_count = 0
            owner.save()
            assert self.permissions_service.user_is_activated(user, owner) is False


class TestUserIsAdminPermissions(TestCase):
    def setUp(self):
        self.permissions_class = UserIsAdminPermissions()

    @patch("internal_api.permissions.get_provider")
    def test_is_admin_on_provider_invokes_torngit_adapter_when_user_not_in_admin_array(
        self, mocked_get_adapter
    ):
        org = OwnerFactory()
        user = OwnerFactory()

        mocked_get_adapter.return_value = GetAdminProviderAdapter()
        self.permissions_class._is_admin_on_provider(user, org)
        assert mocked_get_adapter.return_value.last_call_args == {
            "username": user.username,
            "service_id": user.service_id,
        }

    @patch("internal_api.permissions.get_provider")
    def test_is_admin_on_provider_handles_torngit_exception(self, mock_get_provider):
        code, message = 404, "uh oh"
        mock_get_provider.return_value = GetAdminErrorProviderAdapter(code, message)
        org = OwnerFactory()
        user = OwnerFactory()

        with self.assertRaises(APIException) as e:
            self.permissions_class._is_admin_on_provider(user, org)
