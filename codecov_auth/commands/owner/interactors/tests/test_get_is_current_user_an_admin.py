from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.test import TransactionTestCase, override_settings
from shared.django_apps.codecov_auth.tests.factories import (
    GetAdminProviderAdapter,
    OwnerFactory,
)

from ..get_is_current_user_an_admin import (
    GetIsCurrentUserAnAdminInteractor,
    _is_admin_on_provider,
)


class GetIsCurrentUserAnAdminInteractorTest(TransactionTestCase):
    def setUp(self):
        self.owner_has_admins = OwnerFactory(ownerid=0, admins=[2])
        self.owner_has_no_admins = OwnerFactory(ownerid=1, admins=[])
        self.owner_null_admins = OwnerFactory(ownerid=9, admins=None)

    def test_user_admin_in_personal_org(self):
        current_user = self.owner_has_admins
        owner = self.owner_has_admins
        isAdmin = async_to_sync(
            GetIsCurrentUserAnAdminInteractor(owner, current_user).execute
        )(owner, current_user)
        assert isAdmin == True

    def test_user_not_admin_in_org(self):
        current_user = OwnerFactory(ownerid=3)
        owner = self.owner_has_admins
        isAdmin = async_to_sync(
            GetIsCurrentUserAnAdminInteractor(owner, current_user).execute
        )(owner, current_user)
        assert isAdmin == False

    def test_user_not_a_provider_admin(self):
        current_user = OwnerFactory(ownerid=3)
        owner = self.owner_has_no_admins
        isAdmin = async_to_sync(
            GetIsCurrentUserAnAdminInteractor(owner, current_user).execute
        )(owner, current_user)
        assert isAdmin == False

    @patch(
        "codecov_auth.commands.owner.interactors.get_is_current_user_an_admin.get_provider"
    )
    def test_is_admin_on_provider_invokes_torngit_adapter(self, mocked_get_adapter):
        current_user = OwnerFactory(ownerid=3)
        owner = self.owner_has_no_admins
        mocked_get_adapter.return_value = GetAdminProviderAdapter()
        async_to_sync(_is_admin_on_provider)(owner, current_user)
        assert mocked_get_adapter.return_value.last_call_args == {
            "username": current_user.username,
            "service_id": current_user.service_id,
        }

    @patch(
        "codecov_auth.commands.owner.interactors.get_is_current_user_an_admin.get_provider"
    )
    def test_is_admin_in_org_not_on_provider(self, mocked_get_adapter):
        current_user = OwnerFactory(ownerid=2)
        owner = self.owner_has_admins
        mocked_get_adapter.return_value = GetAdminProviderAdapter(result=False)
        isAdmin = async_to_sync(
            GetIsCurrentUserAnAdminInteractor(owner, current_user).execute
        )(owner, current_user)
        assert isAdmin == True

    @patch(
        "codecov_auth.commands.owner.interactors.get_is_current_user_an_admin.get_provider"
    )
    def test_is_admin_on_provider(self, mocked_get_adapter):
        current_user = OwnerFactory(ownerid=3)
        owner = self.owner_has_no_admins
        mocked_get_adapter.return_value = GetAdminProviderAdapter(result=True)
        isAdmin = async_to_sync(
            GetIsCurrentUserAnAdminInteractor(owner, current_user).execute
        )(owner, current_user)
        assert current_user.ownerid in owner.admins
        assert isAdmin == True

    @patch(
        "codecov_auth.commands.owner.interactors.get_is_current_user_an_admin.get_provider"
    )
    def test_is_admin_on_provider_only_once(self, mocked_get_adapter):
        # Ensure duplicate ownerids won't be saved in admins upon multiple calls
        current_user = OwnerFactory(ownerid=3)
        owner = self.owner_has_no_admins
        mocked_get_adapter.return_value = GetAdminProviderAdapter(result=True)
        async_to_sync(GetIsCurrentUserAnAdminInteractor(owner, current_user).execute)(
            owner, current_user
        )
        async_to_sync(GetIsCurrentUserAnAdminInteractor(owner, current_user).execute)(
            owner, current_user
        )
        assert owner.admins == [3]
        assert current_user.ownerid in owner.admins

    @patch(
        "codecov_auth.commands.owner.interactors.get_is_current_user_an_admin.get_provider"
    )
    def test_admin_on_provider_initially_is_null(self, mocked_get_adapter):
        # Owner model defaults admins to null, check can handle first update
        current_user = OwnerFactory(ownerid=3)
        owner = self.owner_null_admins
        mocked_get_adapter.return_value = GetAdminProviderAdapter(result=True)
        isAdmin = async_to_sync(
            GetIsCurrentUserAnAdminInteractor(owner, current_user).execute
        )(owner, current_user)
        assert owner.admins == [3]
        assert current_user.ownerid in owner.admins
        assert isAdmin == True

    @patch(
        "codecov_auth.commands.owner.interactors.get_is_current_user_an_admin.get_provider"
    )
    def test_is_admin_not_in_org_or_on_provider(self, mocked_get_adapter):
        current_user = OwnerFactory(ownerid=3)
        owner = self.owner_has_no_admins
        mocked_get_adapter.return_value = GetAdminProviderAdapter(result=False)
        isAdmin = async_to_sync(
            GetIsCurrentUserAnAdminInteractor(owner, current_user).execute
        )(owner, current_user)
        assert current_user.ownerid not in owner.admins
        assert isAdmin == False

    @patch("services.self_hosted.is_admin_owner")
    @override_settings(IS_ENTERPRISE=True)
    def test_is_admin_self_hosted(self, is_admin_owner):
        current_user = OwnerFactory(ownerid=3)
        owner = OwnerFactory(ownerid=4)

        is_admin_owner.return_value = False
        is_admin = async_to_sync(
            GetIsCurrentUserAnAdminInteractor(owner, current_user).execute
        )(owner, current_user)
        assert is_admin == False

        is_admin_owner.return_value = True
        is_admin = async_to_sync(
            GetIsCurrentUserAnAdminInteractor(owner, current_user).execute
        )(owner, current_user)
        assert is_admin == True

    def test_is_admin_no_current_owner(self):
        owner = OwnerFactory(ownerid=5)
        res = async_to_sync(GetIsCurrentUserAnAdminInteractor(owner, "gitlab").execute)(
            owner, None
        )
        assert res == False
