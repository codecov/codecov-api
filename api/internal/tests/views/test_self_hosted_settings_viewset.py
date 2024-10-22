from django.test import TestCase, override_settings
from rest_framework.reverse import reverse
from shared.django_apps.core.tests.factories import OwnerFactory

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
