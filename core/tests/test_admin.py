from django.test import TestCase

from codecov_auth.tests.factories import OwnerFactory


class AdminTest(TestCase):
    def setUp(self):
        self.user = OwnerFactory()

    def test_staff_can_access_admin(self):
        self.user.staff = True
        self.user.save()

        self.client.force_login(user=self.user)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)

    def test_non_staff_cannot_access_admin(self):
        self.client.force_login(user=self.user)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)
