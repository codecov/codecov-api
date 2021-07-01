from django.test import TestCase
from django.urls import reverse

from codecov_auth.tests.factories import OwnerFactory


class OwnerAdminTest(TestCase):
    def test_owner_admin_detail_page(self):
        owner = OwnerFactory(staff=True)
        self.client.force_login(user=owner)

        response = self.client.get(
            reverse(f"admin:codecov_auth_owner_change", args=[owner.ownerid])
        )
        self.assertEqual(response.status_code, 200)
