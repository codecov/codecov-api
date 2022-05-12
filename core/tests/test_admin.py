from django.test import TestCase

from codecov_auth.tests.factories import OwnerFactory
from django.contrib.admin.sites import AdminSite

from core.admin import RepositoryAdmin
from core.models import Repository


class AdminTest(TestCase):
    def setUp(self):
        self.user = OwnerFactory()
        self.owner_admin = RepositoryAdmin(Repository, AdminSite)

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

    def test_readonly_fields(self):
        readonly_fields = self.owner_admin.get_readonly_fields(request=None)
        assert "bot" not in readonly_fields
        assert "using_integration" not in readonly_fields
