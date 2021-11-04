from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from codecov_auth.tests.factories import OwnerFactory


class PlansViewSetTests(APITestCase):
    def setUp(self):
        user = OwnerFactory()
        self.client.force_login(user=user)

    def test_list_plans_returns_200_and_plans(self):
        response = self.client.get(reverse("plans-list"))
        assert response.status_code == status.HTTP_200_OK
        assert response.data == [
            {
                "marketing_name": "Basic",
                "value": "users-free",
                "billing_rate": None,
                "base_unit_price": 0,
                "benefits": [
                    "Up to 5 users",
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
                    "Configureable # of users",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                    "Priority Support",
                ],
            },
            {
                "marketing_name": "Pro Team",
                "value": "users-pr-inappy",
                "billing_rate": "annual",
                "base_unit_price": 10,
                "benefits": [
                    "Configureable # of users",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                    "Priority Support",
                ],
            },
        ]
