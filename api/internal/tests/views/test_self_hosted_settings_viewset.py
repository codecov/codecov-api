from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.reverse import reverse

from codecov_auth.models import Owner
from codecov_auth.tests.factories import OwnerFactory
from services.self_hosted import activate_owner, is_autoactivation_enabled
from utils.test_utils import APIClient


@override_settings(IS_ENTERPRISE=True, ROOT_URLCONF="api.internal.enterprise_urls")
class SettingsViewsetUnauthenticatedTestCase(TestCase):
    def test_settings(self):
        res = self.client.get(reverse("selfhosted-users-list"))
        # not authenticated
        assert res.status_code == 401


@override_settings(IS_ENTERPRISE=True, ROOT_URLCONF="api.internal.enterprise_urls")
class SettingsViewsetNonadminTestCase(TestCase):
    def setUp(self):
        self.current_owner = OwnerFactory()
        self.client = APIClient()
        self.client.force_login_owner(self.current_owner)

    def test_settings(self):
        res = self.client.get(reverse("selfhosted-users-list"))
        # not authenticated
        assert res.status_code == 403


@override_settings(IS_ENTERPRISE=True, ROOT_URLCONF="api.internal.enterprise_urls")
class SettingsViewsetTestCase(TestCase):
    def setUp(self):
        self.current_owner = OwnerFactory()
        self.client = APIClient()
        self.client.force_login_owner(self.current_owner)

    @patch("services.self_hosted.license_seats")
    @patch("services.self_hosted.is_autoactivation_enabled")
    @patch("services.self_hosted.admin_owners")
    def test_settings(self, admin_owners, is_autoactivation_enabled, license_seats):
        admin_owners.return_value = Owner.objects.filter(pk__in=[self.current_owner.pk])

        is_autoactivation_enabled.return_value = False
        license_seats.return_value = 5

        res = self.client.get(reverse("selfhosted-settings-detail"))
        assert res.status_code == 200
        assert res.json() == {
            "plan_auto_activate": False,
            "seats_used": 0,
            "seats_limit": 5,
        }

        is_autoactivation_enabled.return_value = True

        org = OwnerFactory()
        owner = OwnerFactory(organizations=[org.pk])
        activate_owner(owner)

        res = self.client.get(reverse("selfhosted-settings-detail"))
        assert res.status_code == 200
        assert res.json() == {
            "plan_auto_activate": True,
            "seats_used": 1,
            "seats_limit": 5,
        }

    @patch("services.self_hosted.admin_owners")
    def test_settings_update(self, admin_owners):
        admin_owners.return_value = Owner.objects.filter(pk__in=[self.current_owner.pk])

        res = self.client.patch(
            reverse("selfhosted-settings-detail"),
            data={"plan_auto_activate": True},
            format="json",
        )
        assert res.status_code == 200
        assert res.json()["plan_auto_activate"] == True
        assert is_autoactivation_enabled() == True

        res = self.client.patch(
            reverse("selfhosted-settings-detail"),
            data={"plan_auto_activate": False},
            format="json",
        )
        assert res.status_code == 200
        assert res.json()["plan_auto_activate"] == False
        assert is_autoactivation_enabled() == False
