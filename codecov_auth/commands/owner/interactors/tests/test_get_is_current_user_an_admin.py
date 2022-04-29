from distutils.util import execute
from unittest.mock import patch

import pytest
from asgiref.sync import async_to_sync
from django.test import TransactionTestCase

from codecov_auth.tests.factories import GetAdminProviderAdapter, OwnerFactory

from ..get_is_current_user_an_admin import (
    GetIsCurrentUserAnAdminInteractor,
    _is_admin_on_provider,
)


class GetIsCurrentUserAnAdminInteractorTest(TransactionTestCase):
    def setUp(self):
        self.owner_has_admins = OwnerFactory(ownerid=0, admins=[2])
        self.owner_has_no_admins = OwnerFactory(ownerid=1, admins=[])

    def test_user_admin_in_personal_org(self):
        current_user = self.owner_has_admins
        owner = self.owner_has_admins
        isAdmin = async_to_sync(
            GetIsCurrentUserAnAdminInteractor(owner, current_user).execute
        )(owner, current_user)
        assert isAdmin == True

    def test_user_admin_in_org(self):
        current_user = OwnerFactory(ownerid=2)
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
        print(mocked_get_adapter.return_value)
        assert mocked_get_adapter.return_value.last_call_args == {
            "username": current_user.username,
            "service_id": current_user.service_id,
        }
