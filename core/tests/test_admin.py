from unittest.mock import MagicMock, patch

from django.contrib.admin.sites import AdminSite
from django.test import TestCase

from codecov_auth.tests.factories import OwnerFactory
from core.admin import RepositoryAdmin
from core.models import Repository
from core.tests.factories import RepositoryFactory


class AdminTest(TestCase):
    def setUp(self):
        self.user = OwnerFactory()
        self.repo_admin = RepositoryAdmin(Repository, AdminSite)

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

    @patch("core.admin.admin.ModelAdmin.log_change")
    def test_prev_and_new_values_in_log_entry(self, mocked_super_log_change):
        repo = RepositoryFactory(using_integration=True)
        repo.save()
        repo.using_integration = False
        form = MagicMock()
        form.changed_data = ["using_integration"]
        self.repo_admin.save_model(
            request=MagicMock, new_repo=repo, form=form, change=True
        )
        assert (
            repo.changed_fields["using_integration"]
            == "prev value: True, new value: False"
        )

        message = []
        message.append({"changed": {"fields": ["using_integration"]}})
        self.repo_admin.log_change(MagicMock, repo, message)
        assert mocked_super_log_change.called_once()
        assert message == [
            {"changed": {"fields": ["using_integration"]}},
            {"using_integration": "prev value: True, new value: False"},
        ]
