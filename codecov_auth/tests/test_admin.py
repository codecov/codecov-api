from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.test import TestCase
from django.urls import reverse

from codecov_auth.models import Service
from codecov_auth.tests.factories import OwnerFactory


class OwnerAdminTest(TestCase):
    def setUp(self):
        self.staff_user = OwnerFactory(staff=True)
        self.client.force_login(user=self.staff_user)

    def test_owner_admin_detail_page(self):
        response = self.client.get(
            reverse(f"admin:codecov_auth_owner_change", args=[self.staff_user.ownerid])
        )
        self.assertEqual(response.status_code, 200)

    def test_owner_admin_impersonate_owner(self):
        user_to_impersonate = OwnerFactory(
            username="impersonate_me", service=Service.BITBUCKET.value
        )
        other_user = OwnerFactory()

        with self.subTest("more than one user selected"):
            response = self.client.post(
                reverse(f"admin:codecov_auth_owner_changelist"),
                {
                    "action": "impersonate_owner",
                    ACTION_CHECKBOX_NAME: [
                        user_to_impersonate.ownerid,
                        other_user.ownerid,
                    ],
                },
                follow=True,
            )
            self.assertIn(
                "You must impersonate exactly one Owner.", str(response.content)
            )

        with self.subTest("one user selected"):
            response = self.client.post(
                reverse(f"admin:codecov_auth_owner_changelist"),
                {
                    "action": "impersonate_owner",
                    ACTION_CHECKBOX_NAME: [user_to_impersonate.ownerid],
                },
            )
            self.assertIn("/bb/", response.url)
            self.assertEqual(response.cookies.get("staff_user").value, "impersonate_me")
