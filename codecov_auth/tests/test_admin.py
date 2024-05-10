from unittest.mock import MagicMock, patch

from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase
from django.urls import reverse

from codecov.commands.exceptions import ValidationError
from codecov_auth.admin import OrgUploadTokenInline, OwnerAdmin, UserAdmin
from codecov_auth.models import OrganizationLevelToken, Owner, SentryUser, User
from codecov_auth.tests.factories import (
    OrganizationLevelTokenFactory,
    OwnerFactory,
    SentryUserFactory,
    UserFactory,
)
from plan.constants import (
    ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS,
    PlanName,
    TrialStatus,
)
from utils.test_utils import APIClient


class OwnerAdminTest(TestCase):
    def setUp(self):
        self.staff_user = UserFactory(is_staff=True)
        self.client.force_login(user=self.staff_user)
        admin_site = AdminSite()
        admin_site.register(OrganizationLevelToken)
        self.owner_admin = OwnerAdmin(Owner, admin_site)

    def test_owner_admin_detail_page(self):
        owner = OwnerFactory()
        response = self.client.get(
            reverse("admin:codecov_auth_owner_change", args=[owner.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_owner_admin_impersonate_owner(self):
        owner_to_impersonate = OwnerFactory(service="bitbucket")
        other_owner = OwnerFactory()

        with self.subTest("more than one user selected"):
            response = self.client.post(
                reverse("admin:codecov_auth_owner_changelist"),
                {
                    "action": "impersonate_owner",
                    ACTION_CHECKBOX_NAME: [
                        owner_to_impersonate.pk,
                        other_owner.pk,
                    ],
                },
                follow=True,
            )
            self.assertIn(
                "You must impersonate exactly one Owner.", str(response.content)
            )

        with self.subTest("one user selected"):
            response = self.client.post(
                reverse("admin:codecov_auth_owner_changelist"),
                {
                    "action": "impersonate_owner",
                    ACTION_CHECKBOX_NAME: [owner_to_impersonate.pk],
                },
            )
            self.assertIn("/bb/", response.url)
            self.assertEqual(
                response.cookies.get("staff_user").value,
                str(owner_to_impersonate.pk),
            )

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
            request=MagicMock, new_obj=owner, form=form, change=True
        )
        assert owner.changed_fields["staff"] == "prev value: True, new value: False"

        message = []
        message.append({"changed": {"fields": ["staff"]}})
        self.owner_admin.log_change(MagicMock, owner, message)
        mocked_super_log_change.assert_called_once()
        assert message == [
            {"changed": {"fields": ["staff"]}},
            {"staff": "prev value: True, new value: False"},
        ]

    def test_inline_orgwide_tokens_display(self):
        owner = OwnerFactory()
        request_url = reverse("admin:codecov_auth_owner_change", args=[owner.ownerid])
        request = RequestFactory().get(request_url)
        request.user = self.staff_user
        inlines = self.owner_admin.get_inline_instances(request, owner)
        # Orgs in enterprise cloud have a token created automagically
        assert isinstance(inlines[0], OrgUploadTokenInline)

    def test_inline_orgwide_permissions(self):
        owner_in_cloud_plan = OwnerFactory(plan="users-enterprisey")
        org_token = OrganizationLevelTokenFactory(owner=owner_in_cloud_plan)
        owner_in_cloud_plan.save()
        org_token.save()
        request_url = reverse(
            "admin:codecov_auth_owner_change", args=[owner_in_cloud_plan.ownerid]
        )
        request = RequestFactory().get(request_url)
        request.user = self.staff_user
        inlines = self.owner_admin.get_inline_instances(request, owner_in_cloud_plan)
        inline_instance = inlines[0]
        assert (
            inline_instance.has_add_permission(request, owner_in_cloud_plan) == False
        )  # Should be false because it already has a token
        assert (
            inline_instance.has_delete_permission(request, owner_in_cloud_plan) == True
        )
        assert (
            inline_instance.has_change_permission(request, owner_in_cloud_plan) == False
        )

    def test_inline_orgwide_add_token_permission_no_token_and_user_in_enterprise_cloud_plan(
        self,
    ):
        owner = OwnerFactory()
        assert owner.plan not in ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS
        assert OrganizationLevelToken.objects.filter(owner=owner).count() == 0
        request_url = reverse("admin:codecov_auth_owner_change", args=[owner.ownerid])
        request = RequestFactory().get(request_url)
        request.user = self.staff_user
        inlines = self.owner_admin.get_inline_instances(request, owner)
        inline_instance = inlines[0]
        assert inline_instance.has_add_permission(request, owner) == True

    def test_inline_orgwide_add_token_permission_no_token_user_not_in_enterprise_cloud_plan(
        self,
    ):
        owner_in_cloud_plan = OwnerFactory(plan="users-enterprisey")
        assert (
            OrganizationLevelToken.objects.filter(owner=owner_in_cloud_plan).count()
            == 0
        )
        request_url = reverse(
            "admin:codecov_auth_owner_change", args=[owner_in_cloud_plan.ownerid]
        )
        request = RequestFactory().get(request_url)
        request.user = self.staff_user
        inlines = self.owner_admin.get_inline_instances(request, owner_in_cloud_plan)
        inline_instance = inlines[0]
        assert inline_instance.has_add_permission(request, owner_in_cloud_plan) == True

    @patch(
        "codecov_auth.services.org_level_token_service.OrgLevelTokenService.refresh_token"
    )
    def test_org_token_refresh_request_calls_service_to_refresh_token(
        self, mock_refresh
    ):
        owner_in_cloud_plan = OwnerFactory(plan="users-enterprisey")
        org_token = OrganizationLevelTokenFactory(owner=owner_in_cloud_plan)
        owner_in_cloud_plan.save()
        org_token.save()
        request_url = reverse(
            "admin:codecov_auth_owner_change", args=[owner_in_cloud_plan.ownerid]
        )
        fake_data = {
            "staff": ["true"],
            "plan": ["users-enterprisem"],
            "plan_provider": [""],
            "plan_user_count": ["5"],
            "plan_activated_users": [""],
            "integration_id": [""],
            "bot": [""],
            "stripe_customer_id": [""],
            "stripe_subscription_id": [""],
            "organizations": [""],
            "organization_tokens-TOTAL_FORMS": ["1"],
            "organization_tokens-INITIAL_FORMS": ["0"],
            "organization_tokens-MIN_NUM_FORMS": ["0"],
            "organization_tokens-MAX_NUM_FORMS": ["1"],
            "organization_tokens-0-id": [str(org_token.id)],
            "organization_tokens-0-owner": [owner_in_cloud_plan.ownerid],
            "organization_tokens-0-valid_until_0": ["2023-08-08"],
            "organization_tokens-0-valid_until_1": ["17:01:14"],
            "organization_tokens-0-token_type": ["upload"],
            "organization_tokens-0-REFRESH": "on",
            "_continue": ["Save and continue editing"],
        }
        response = self.client.post(request_url, data=fake_data)
        mock_refresh.assert_called_with(str(org_token.id))

    @patch(
        "codecov_auth.services.org_level_token_service.OrgLevelTokenService.refresh_token"
    )
    def test_org_token_request_doesnt_call_service_to_refresh_token(self, mock_refresh):
        owner_in_cloud_plan = OwnerFactory(plan="users-enterprisey")
        org_token = OrganizationLevelTokenFactory(owner=owner_in_cloud_plan)
        owner_in_cloud_plan.save()
        org_token.save()
        request_url = reverse(
            "admin:codecov_auth_owner_change", args=[owner_in_cloud_plan.ownerid]
        )
        fake_data = {
            "staff": ["true"],
            "plan": ["users-enterprisem"],
            "plan_provider": [""],
            "plan_user_count": ["5"],
            "plan_activated_users": [""],
            "integration_id": [""],
            "bot": [""],
            "stripe_customer_id": [""],
            "stripe_subscription_id": [""],
            "organizations": [""],
            "organization_tokens-TOTAL_FORMS": ["1"],
            "organization_tokens-INITIAL_FORMS": ["0"],
            "organization_tokens-MIN_NUM_FORMS": ["0"],
            "organization_tokens-MAX_NUM_FORMS": ["1"],
            "organization_tokens-0-id": [str(org_token.id)],
            "organization_tokens-0-owner": [owner_in_cloud_plan.ownerid],
            "organization_tokens-0-valid_until_0": ["2023-08-08"],
            "organization_tokens-0-valid_until_1": ["17:01:14"],
            "organization_tokens-0-token_type": ["upload"],
            "_continue": ["Save and continue editing"],
        }
        response = self.client.post(request_url, data=fake_data)
        mock_refresh.assert_not_called()

    def test_start_trial_ui_display(self):
        owner = OwnerFactory()

        res = self.client.post(
            reverse("admin:codecov_auth_owner_changelist"),
            {
                "action": "extend_trial",
                ACTION_CHECKBOX_NAME: [owner.pk],
            },
        )
        assert res.status_code == 200
        assert "Extending trial for:" in str(res.content)

    @patch("plan.service.PlanService.start_trial_manually")
    def test_start_trial_action(self, mock_start_trial_service):
        mock_start_trial_service.return_value = None
        org_to_be_trialed = OwnerFactory()

        res = self.client.post(
            reverse("admin:codecov_auth_owner_changelist"),
            {
                "action": "extend_trial",
                ACTION_CHECKBOX_NAME: [org_to_be_trialed.pk],
                "end_date": "2024-01-01 01:02:03",
                "extend_trial": True,
            },
        )
        assert res.status_code == 302
        assert mock_start_trial_service.called

    @patch("plan.service.PlanService._start_trial_helper")
    def test_extend_trial_action(self, mock_start_trial_service):
        mock_start_trial_service.return_value = None
        org_to_be_trialed = OwnerFactory()
        org_to_be_trialed.plan = PlanName.TRIAL_PLAN_NAME.value
        org_to_be_trialed.save()

        res = self.client.post(
            reverse("admin:codecov_auth_owner_changelist"),
            {
                "action": "extend_trial",
                ACTION_CHECKBOX_NAME: [org_to_be_trialed.pk],
                "end_date": "2024-01-01 01:02:03",
                "extend_trial": True,
            },
        )
        assert res.status_code == 302
        assert mock_start_trial_service.called
        assert mock_start_trial_service.call_args.kwargs == {"is_extension": True}

    @patch("plan.service.PlanService.start_trial_manually")
    def test_start_trial_paid_plan(self, mock_start_trial_service):
        mock_start_trial_service.side_effect = ValidationError(
            "Cannot trial from a paid plan"
        )

        org_to_be_trialed = OwnerFactory()

        res = self.client.post(
            reverse("admin:codecov_auth_owner_changelist"),
            {
                "action": "extend_trial",
                ACTION_CHECKBOX_NAME: [org_to_be_trialed.pk],
                "end_date": "2024-01-01 01:02:03",
                "extend_trial": True,
            },
        )
        assert res.status_code == 302
        assert mock_start_trial_service.called


class UserAdminTest(TestCase):
    def setUp(self):
        self.staff_user = UserFactory(is_staff=True)
        self.client.force_login(user=self.staff_user)
        admin_site = AdminSite()
        admin_site.register(User)
        self.owner_admin = UserAdmin(User, admin_site)

    def test_user_admin_list_page(self):
        user = UserFactory()
        res = self.client.get(reverse("admin:codecov_auth_user_changelist"))
        assert res.status_code == 200
        assert user.name in res.content.decode("utf-8")
        assert user.email in res.content.decode("utf-8")

    def test_user_admin_detail_page(self):
        user = UserFactory()
        res = self.client.get(reverse("admin:codecov_auth_user_change", args=[user.pk]))
        assert res.status_code == 200
        assert user.name in res.content.decode("utf-8")
        assert user.email in res.content.decode("utf-8")
        assert str(user.external_id) in res.content.decode("utf-8")


class SentryUserAdminTest(TestCase):
    def setUp(self) -> None:
        self.staff_user = UserFactory(is_staff=True)
        self.client.force_login(user=self.staff_user)
        admin_site = AdminSite()
        admin_site.register(User)
        admin_site.register(SentryUser)
        self.owner_admin = UserAdmin(User, admin_site)

    def test_user_admin_list_page(self):
        sentry_user = SentryUserFactory()
        res = self.client.get(reverse("admin:codecov_auth_sentryuser_changelist"))
        assert res.status_code == 200
        content = res.content.decode("utf-8")
        assert sentry_user.name in res.content.decode("utf-8")
        assert sentry_user.email in res.content.decode("utf-8")

    def test_user_admin_detail_page(self):
        sentry_user = SentryUserFactory()
        res = self.client.get(
            reverse("admin:codecov_auth_sentryuser_change", args=[sentry_user.pk])
        )
        assert res.status_code == 200
        assert sentry_user.name in res.content.decode("utf-8")
        assert sentry_user.email in res.content.decode("utf-8")
        assert sentry_user.access_token not in res.content.decode("utf-8")
        assert sentry_user.refresh_token not in res.content.decode("utf-8")
