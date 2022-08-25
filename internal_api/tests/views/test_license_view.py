from datetime import datetime
from unittest.mock import patch

from django.test import RequestFactory, override_settings
from rest_framework.reverse import reverse
from shared.license import LicenseInformation

from codecov.tests.base_test import InternalAPITest
from codecov_auth.tests.factories import OwnerFactory
from internal_api.license.views import LicenseView


class LicenseViewTest(InternalAPITest):
    def setUp(self):
        self.user = OwnerFactory()
        self.client.force_login(user=self.user)

    @patch("internal_api.license.views.get_current_license")
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

    @override_settings(ROOT_URLCONF="internal_api.enterprise_urls")
    @patch("internal_api.license.views.get_current_license")
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
