from unittest.mock import patch

from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from codecov_auth.tests.factories import OwnerFactory


class PlansViewSetTests(APITestCase):
    def setUp(self):
        self.user = OwnerFactory()
        self.client.force_login(user=self.user)

    def test_list_plans_returns_200_and_plans(self):
        response = self.client.get(reverse("plans-list"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data == [
            {
                "marketing_name": "Free",
                "value": "users-free",
                "billing_rate": None,
                "base_unit_price": 0,
                "benefits": [
                    "Up to 1 user",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                ],
            },
            {
                "marketing_name": "Basic",
                "value": "users-basic",
                "billing_rate": None,
                "base_unit_price": 0,
                "monthly_uploads_limit": 250,
                "benefits": [
                    "Up to 1 user",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                ],
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
            },
        ]

    @patch("services.sentry.is_sentry_user")
    def test_list_plans_sentry_user(self, is_sentry_user):
        is_sentry_user.return_value = True
        response = self.client.get(reverse("plans-list"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data == [
            {
                "marketing_name": "Free",
                "value": "users-free",
                "billing_rate": None,
                "base_unit_price": 0,
                "benefits": [
                    "Up to 1 user",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                ],
            },
            {
                "marketing_name": "Basic",
                "value": "users-basic",
                "billing_rate": None,
                "base_unit_price": 0,
                "monthly_uploads_limit": 250,
                "benefits": [
                    "Up to 1 user",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                ],
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
            },
            {
                "marketing_name": "Sentry Pro Team",
                "value": "users-sentrym",
                "billing_rate": "monthly",
                "base_unit_price": 12,
                "benefits": [
                    "Configurable # of users",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                    "Priority Support",
                ],
                "trial_days": 14,
            },
            {
                "marketing_name": "Sentry Pro Team",
                "value": "users-sentryy",
                "billing_rate": "annually",
                "base_unit_price": 10,
                "benefits": [
                    "Configurable # of users",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                    "Priority Support",
                ],
                "trial_days": 14,
            },
        ]
        is_sentry_user.assert_called_once_with(self.user)
