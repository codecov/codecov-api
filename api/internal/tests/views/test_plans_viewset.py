from unittest.mock import patch

from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from codecov_auth.tests.factories import OwnerFactory
from utils.test_utils import Client


class PlansViewSetTests(APITestCase):
    def setUp(self):
        self.current_owner = OwnerFactory()
        self.client = Client()
        self.client.force_login_owner(self.current_owner)

    def test_list_plans_returns_200_and_plans(self):
        response = self.client.get(reverse("plans-list"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data == [
            {
                "marketing_name": "Developer",
                "value": "users-free",
                "billing_rate": None,
                "base_unit_price": 0,
                "benefits": [
                    "Up to 1 user",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                ],
                "monthly_uploads_limit": None,
                "trial_days": None,
            },
            {
                "marketing_name": "Developer",
                "value": "users-basic",
                "billing_rate": None,
                "base_unit_price": 0,
                "benefits": [
                    "Up to 1 user",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                ],
                "monthly_uploads_limit": 250,
                "trial_days": None,
            },
            {
                "marketing_name": "Pro Team",
                "value": "users-pr-inappm",
                "billing_rate": "monthly",
                "base_unit_price": 12,
                "benefits": [
                    "Configurable # of users",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                    "Priority Support",
                ],
                "monthly_uploads_limit": None,
                "trial_days": None,
            },
            {
                "marketing_name": "Pro Team",
                "value": "users-pr-inappy",
                "billing_rate": "annually",
                "base_unit_price": 10,
                "benefits": [
                    "Configurable # of users",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                    "Priority Support",
                ],
                "monthly_uploads_limit": None,
                "trial_days": None,
            },
        ]

    @patch("services.sentry.is_sentry_user")
    def test_list_plans_sentry_user(self, is_sentry_user):
        is_sentry_user.return_value = True

        response = self.client.get(reverse("plans-list"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data == [
            {
                "marketing_name": "Developer",
                "value": "users-free",
                "billing_rate": None,
                "base_unit_price": 0,
                "benefits": [
                    "Up to 1 user",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                ],
                "monthly_uploads_limit": None,
                "trial_days": None,
            },
            {
                "marketing_name": "Developer",
                "value": "users-basic",
                "billing_rate": None,
                "base_unit_price": 0,
                "benefits": [
                    "Up to 1 user",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                ],
                "monthly_uploads_limit": 250,
                "trial_days": None,
            },
            {
                "marketing_name": "Pro Team",
                "value": "users-pr-inappm",
                "billing_rate": "monthly",
                "base_unit_price": 12,
                "benefits": [
                    "Configurable # of users",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                    "Priority Support",
                ],
                "monthly_uploads_limit": None,
                "trial_days": None,
            },
            {
                "marketing_name": "Pro Team",
                "value": "users-pr-inappy",
                "billing_rate": "annually",
                "base_unit_price": 10,
                "benefits": [
                    "Configurable # of users",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                    "Priority Support",
                ],
                "monthly_uploads_limit": None,
                "trial_days": None,
            },
            {
                "marketing_name": "Pro Team for Sentry",
                "value": "users-sentrym",
                "billing_rate": "monthly",
                "base_unit_price": 12,
                "benefits": [
                    "Includes 5 seats",
                    "$12 per additional seat",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                    "Priority Support",
                ],
                "monthly_uploads_limit": None,
                "trial_days": 14,
            },
            {
                "marketing_name": "Pro Team for Sentry",
                "value": "users-sentryy",
                "billing_rate": "annually",
                "base_unit_price": 10,
                "benefits": [
                    "Includes 5 seats",
                    "$10 per additional seat",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                    "Priority Support",
                ],
                "monthly_uploads_limit": None,
                "trial_days": 14,
            },
        ]
        is_sentry_user.assert_called_once_with(self.current_owner)

    def test_list_plans_anonymous_user(self):
        self.client.logout()

        response = self.client.get(reverse("plans-list"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data == [
            {
                "marketing_name": "Developer",
                "value": "users-free",
                "billing_rate": None,
                "base_unit_price": 0,
                "benefits": [
                    "Up to 1 user",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                ],
                "monthly_uploads_limit": None,
                "trial_days": None,
            },
            {
                "marketing_name": "Developer",
                "value": "users-basic",
                "billing_rate": None,
                "base_unit_price": 0,
                "benefits": [
                    "Up to 1 user",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                ],
                "monthly_uploads_limit": 250,
                "trial_days": None,
            },
            {
                "marketing_name": "Pro Team",
                "value": "users-pr-inappm",
                "billing_rate": "monthly",
                "base_unit_price": 12,
                "benefits": [
                    "Configurable # of users",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                    "Priority Support",
                ],
                "monthly_uploads_limit": None,
                "trial_days": None,
            },
            {
                "marketing_name": "Pro Team",
                "value": "users-pr-inappy",
                "billing_rate": "annually",
                "base_unit_price": 10,
                "benefits": [
                    "Configurable # of users",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                    "Priority Support",
                ],
                "monthly_uploads_limit": None,
                "trial_days": None,
            },
        ]
