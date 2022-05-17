from unittest.mock import MagicMock, patch

from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.admin.sites import AdminSite
from django.test import TestCase
from django.urls import reverse

from codecov_auth.admin import OwnerAdmin
from codecov_auth.models import Owner, Service
from codecov_auth.tests.factories import OwnerFactory


class OwnerAdminTest(TestCase):
    def setUp(self):
        self.staff_user = OwnerFactory(staff=True)
        self.client.force_login(user=self.staff_user)
        self.owner_admin = OwnerAdmin(Owner, AdminSite)

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

    @patch("codecov_auth.admin.TaskService.delete_owner")
    def test_delete_queryset(self, delete_mock):
        user_to_delete = OwnerFactory()
        ownerid = user_to_delete.ownerid
        queryset = MagicMock()
        queryset.__iter__.return_value = [user_to_delete]

        self.owner_admin.delete_queryset(MagicMock(), queryset)

        delete_mock.assert_called_once_with(ownerid=ownerid)

    @patch("codecov_auth.admin.TaskService.delete_owner")
    def test_delete_model(self, delete_mock):
        user_to_delete = OwnerFactory()
        ownerid = user_to_delete.ownerid
        self.owner_admin.delete_model(MagicMock(), user_to_delete)
        delete_mock.assert_called_once_with(ownerid=ownerid)

    @patch("codecov_auth.admin.admin.ModelAdmin.get_deleted_objects")
    def test_confirmation_deleted_objects(self, mocked_deleted_objs):

        user_to_delete = OwnerFactory()
        deleted_objs = [
            'Owner: <a href="/admin/codecov_auth/owner/{}/change/">{};</a>'.format(
                user_to_delete.ownerid, user_to_delete
            )
        ]
        mocked_deleted_objs.return_value = deleted_objs, {"owners": 1}, set(), []

        (
            deleted_objects,
            model_count,
            perms_needed,
            protected,
        ) = self.owner_admin.get_deleted_objects([user_to_delete], MagicMock())

        mocked_deleted_objs.assert_called_once()
        assert deleted_objects == ()

    @patch("codecov_auth.admin.admin.ModelAdmin.log_change")
    def test_prev_and_new_values_in_log_entry(self, mocked_super_log_change):
        owner = OwnerFactory(staff=True)
        owner.save()
        owner.staff = False
        form = MagicMock()
        form.changed_data = ["staff"]
        self.owner_admin.save_model(
            request=MagicMock, new_owner=owner, form=form, change=True
        )
        assert owner.changed_fields["staff"] == "prev value: True, new value: False"

        message = []
        message.append({"changed": {"fields": ["staff"]}})
        self.owner_admin.log_change(MagicMock, owner, message)
        assert mocked_super_log_change.called_once()
        assert message == [
            {"changed": {"fields": ["staff"]}},
            {"staff": "prev value: True, new value: False"},
        ]
