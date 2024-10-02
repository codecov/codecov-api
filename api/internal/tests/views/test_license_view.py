from datetime import datetime
from unittest.mock import patch

from django.test import RequestFactory, override_settings
from rest_framework.reverse import reverse
from shared.django_apps.core.tests.factories import OwnerFactory
from shared.license import LicenseInformation

from api.internal.license.views import LicenseView
from codecov.tests.base_test import InternalAPITest
from utils.test_utils import Client


class LicenseViewTest(InternalAPITest):
    def setUp(self):
        self.current_owner = OwnerFactory()
        self.client = Client()
        self.client.force_login_owner(self.current_owner)

    @patch("api.internal.license.views.get_current_license")
    def test_license_view(self, mocked_license):
        mocked_license.return_value = LicenseInformation(
            is_valid=True,
            message=None,
            url="https://codeov.mysite.com",
            number_allowed_users=5,
            number_allowed_repos=10,
            expires=datetime.strptime("2020-05-09 00:00:00", "%Y-%m-%d %H:%M:%S"),
            is_trial=True,
            is_pr_billing=False,
        )

        request = RequestFactory().get("/")
        view = LicenseView()
        view.setup(request)
        response = view.get(request)

        expected_result = {
            "trial": True,
            "url": "https://codeov.mysite.com",
            "users": 5,
            "repos": 10,
            "expires_at": "2020-05-09T00:00:00Z",
            "pr_billing": False,
        }

        assert response.data == expected_result

    @override_settings(ROOT_URLCONF="api.internal.enterprise_urls")
    @patch("api.internal.license.views.get_current_license")
    def test_license_url(self, mocked_license):
        mocked_license.return_value = LicenseInformation(
            is_valid=True,
            message=None,
            url=None,
            number_allowed_users=5,
            number_allowed_repos=None,
            expires=datetime.strptime("2020-05-09 00:00:00", "%Y-%m-%d %H:%M:%S"),
            is_trial=True,
            is_pr_billing=False,
        )

        response = self.client.get(
            reverse(
                "license",
            )
        )

        expected_result = {
            "trial": True,
            "url": None,
            "users": 5,
            "repos": None,
            "expires_at": "2020-05-09T00:00:00Z",
            "pr_billing": False,
        }

        assert response.data == expected_result
