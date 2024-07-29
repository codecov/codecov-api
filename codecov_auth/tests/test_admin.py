from unittest.mock import MagicMock, patch

from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase
from django.urls import reverse
from shared.django_apps.codecov_auth.models import (
    Account,
    AccountsUsers,
    InvoiceBilling,
    StripeBilling,
)
from shared.django_apps.codecov_auth.tests.factories import (
    AccountFactory,
    InvoiceBillingFactory,
    StripeBillingFactory,
)

from codecov.commands.exceptions import ValidationError
from codecov_auth.admin import (
    AccountAdmin,
    InvoiceBillingAdmin,
    OrgUploadTokenInline,
    OwnerAdmin,
    StripeBillingAdmin,
    UserAdmin,
)
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
)


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
        self.client.post(request_url, data=fake_data)
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
        self.client.post(request_url, data=fake_data)
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

    def test_account_widget(self):
        owner = OwnerFactory(user=UserFactory(), plan="users-enterprisey")
        rf = RequestFactory()
        get_request = rf.get(f"/admin/codecov_auth/owner/{owner.ownerid}/change/")
        get_request.user = self.staff_user
        sample_input = {
            "change": True,
            "fields": ["account", "plan", "uses_invoice", "staff"],
        }
        form = self.owner_admin.get_form(request=get_request, obj=owner, **sample_input)
        # admin user cannot create, edit, or delete Account objects from the OwnerAdmin
        self.assertFalse(form.base_fields["account"].widget.can_add_related)
        self.assertFalse(form.base_fields["account"].widget.can_change_related)
        self.assertFalse(form.base_fields["account"].widget.can_delete_related)


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
        res.content.decode("utf-8")
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


class AccountAdminTest(TestCase):
    def setUp(self):
        staff_user = UserFactory(is_staff=True)
        self.client.force_login(user=staff_user)
        admin_site = AdminSite()
        admin_site.register(Account)
        admin_site.register(StripeBilling)
        admin_site.register(InvoiceBilling)
        admin_site.register(AccountsUsers)
        self.account_admin = AccountAdmin(Account, admin_site)

        self.account = AccountFactory(plan_seat_count=4, free_seat_count=2)
        self.org_1 = OwnerFactory(account=self.account)
        self.org_2 = OwnerFactory(account=self.account)
        self.owner_with_user_1 = OwnerFactory(user=UserFactory())
        self.owner_with_user_2 = OwnerFactory(user=UserFactory())
        self.owner_with_user_3 = OwnerFactory(user=UserFactory())
        self.owner_without_user_1 = OwnerFactory(user=None)
        self.owner_without_user_2 = OwnerFactory(user=None)
        self.student = OwnerFactory(user=UserFactory(), student=True)
        self.org_1.plan_activated_users = [
            self.owner_with_user_2.ownerid,
            self.owner_with_user_3.ownerid,
            self.owner_without_user_1.ownerid,
            self.student.ownerid,
            self.owner_without_user_2.ownerid,
        ]
        self.org_2.plan_activated_users = [
            self.owner_with_user_2.ownerid,
            self.owner_with_user_3.ownerid,
            self.owner_without_user_1.ownerid,
            self.student.ownerid,
            self.owner_with_user_1.ownerid,
        ]
        self.org_1.save()
        self.org_2.save()

    def test_list_page(self):
        res = self.client.get(reverse("admin:codecov_auth_account_changelist"))
        self.assertEqual(res.status_code, 200)
        decoded_res = res.content.decode("utf-8")
        self.assertIn("column-name", decoded_res)
        self.assertIn("column-is_active", decoded_res)
        self.assertIn(
            '<a href="/admin/codecov_auth/account/add/" class="addlink">', decoded_res
        )
        self.assertIn(
            '<option value="link_users_to_account">Link Users to Account</option>',
            decoded_res,
        )

    def test_detail_page(self):
        res = self.client.get(
            reverse("admin:codecov_auth_account_change", args=[self.account.pk])
        )
        self.assertEqual(res.status_code, 200)
        decoded_res = res.content.decode("utf-8")
        self.assertIn(
            '<option value="users-basic" selected>BASIC_PLAN_NAME</option>', decoded_res
        )
        self.assertIn("Organizations (read only)", decoded_res)
        self.assertIn("Stripe Billing (click save to commit changes)", decoded_res)
        self.assertIn("Invoice Billing (click save to commit changes)", decoded_res)

    def test_link_users_to_account(self):
        self.assertEqual(AccountsUsers.objects.all().count(), 0)
        self.assertEqual(self.account.accountsusers_set.all().count(), 0)

        res = self.client.post(
            reverse("admin:codecov_auth_account_changelist"),
            {
                "action": "link_users_to_account",
                ACTION_CHECKBOX_NAME: [self.account.pk],
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, "/admin/codecov_auth/account/")
        messages = list(res.wsgi_request._messages)
        self.assertEqual(messages[0].message, "Created a User for 2 Owners")
        self.assertEqual(
            messages[1].message, "Created 6 AccountsUsers, removed 0 AccountsUsers"
        )

        self.assertEqual(AccountsUsers.objects.all().count(), 6)
        self.assertEqual(
            AccountsUsers.objects.filter(account_id=self.account.id).count(), 6
        )

        for org in [self.org_1, self.org_2]:
            for active_owner_id in org.plan_activated_users:
                owner_obj = Owner.objects.get(pk=active_owner_id)
                self.assertTrue(
                    AccountsUsers.objects.filter(
                        account=self.account, user_id=owner_obj.user_id
                    ).exists()
                )

        # another user joins
        another_owner_with_user = OwnerFactory(user=UserFactory())
        self.org_1.plan_activated_users.append(another_owner_with_user.ownerid)
        self.org_1.save()
        # rerun action to re-sync
        res = self.client.post(
            reverse("admin:codecov_auth_account_changelist"),
            {
                "action": "link_users_to_account",
                ACTION_CHECKBOX_NAME: [self.account.pk],
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, "/admin/codecov_auth/account/")
        messages = list(res.wsgi_request._messages)
        self.assertEqual(messages[2].message, "Created a User for 0 Owners")
        self.assertEqual(
            messages[3].message, "Created 1 AccountsUsers, removed 0 AccountsUsers"
        )

        self.assertEqual(AccountsUsers.objects.all().count(), 7)
        self.assertEqual(
            AccountsUsers.objects.filter(account_id=self.account.id).count(), 7
        )
        self.assertIn(
            another_owner_with_user.user_id,
            self.account.accountsusers_set.all().values_list("user_id", flat=True),
        )

    def test_link_users_to_account_not_enough_seats(self):
        self.assertEqual(AccountsUsers.objects.all().count(), 0)
        self.account.plan_seat_count = 1
        self.account.save()
        res = self.client.post(
            reverse("admin:codecov_auth_account_changelist"),
            {
                "action": "link_users_to_account",
                ACTION_CHECKBOX_NAME: [self.account.pk],
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, "/admin/codecov_auth/account/")
        messages = list(res.wsgi_request._messages)
        self.assertEqual(
            messages[0].message,
            "Request failed: Account plan does not have enough seats; current plan activated users (non-students): 5, total seats for account: 3",
        )
        self.assertEqual(AccountsUsers.objects.all().count(), 0)

    def test_seat_check(self):
        self.assertEqual(AccountsUsers.objects.all().count(), 0)
        self.account.plan_seat_count = 1
        self.account.save()
        res = self.client.post(
            reverse("admin:codecov_auth_account_changelist"),
            {
                "action": "seat_check",
                ACTION_CHECKBOX_NAME: [self.account.pk],
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, "/admin/codecov_auth/account/")
        messages = list(res.wsgi_request._messages)
        self.assertEqual(
            messages[0].message,
            "Request failed: Account plan does not have enough seats; current plan activated users (non-students): 5, total seats for account: 3",
        )

        self.account.plan_seat_count = 10
        self.account.save()
        res = self.client.post(
            reverse("admin:codecov_auth_account_changelist"),
            {
                "action": "seat_check",
                ACTION_CHECKBOX_NAME: [self.account.pk],
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, "/admin/codecov_auth/account/")
        messages = list(res.wsgi_request._messages)
        self.assertEqual(
            messages[1].message,
            "Request succeeded: Account plan has enough seats! current plan activated users (non-students): 5, total seats for account: 12",
        )
        self.assertEqual(AccountsUsers.objects.all().count(), 0)

    def test_link_users_to_account_remove_unneeded_account_users(self):
        res = self.client.post(
            reverse("admin:codecov_auth_account_changelist"),
            {
                "action": "link_users_to_account",
                ACTION_CHECKBOX_NAME: [self.account.pk],
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, "/admin/codecov_auth/account/")
        messages = list(res.wsgi_request._messages)
        self.assertEqual(messages[0].message, "Created a User for 2 Owners")
        self.assertEqual(
            messages[1].message, "Created 6 AccountsUsers, removed 0 AccountsUsers"
        )

        self.assertEqual(AccountsUsers.objects.all().count(), 6)
        self.assertEqual(
            AccountsUsers.objects.filter(account_id=self.account.id).count(), 6
        )

        for org in [self.org_1, self.org_2]:
            for active_owner_id in org.plan_activated_users:
                owner_obj = Owner.objects.get(pk=active_owner_id)
                self.assertTrue(
                    AccountsUsers.objects.filter(
                        account=self.account, user_id=owner_obj.user_id
                    ).exists()
                )

        # disconnect one of the orgs
        self.org_2.account = None
        self.org_2.save()

        # re-sync to remove Account users from org 2 that are not connected to other account orgs (just owner_with_user_1)
        res = self.client.post(
            reverse("admin:codecov_auth_account_changelist"),
            {
                "action": "link_users_to_account",
                ACTION_CHECKBOX_NAME: [self.account.pk],
            },
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, "/admin/codecov_auth/account/")
        messages = list(res.wsgi_request._messages)
        self.assertEqual(messages[2].message, "Created a User for 0 Owners")
        self.assertEqual(
            messages[3].message, "Created 0 AccountsUsers, removed 1 AccountsUsers"
        )

        self.assertEqual(AccountsUsers.objects.all().count(), 5)
        self.assertEqual(
            AccountsUsers.objects.filter(account_id=self.account.id).count(), 5
        )
        still_connected = [
            self.owner_with_user_2,
            self.owner_with_user_3,
            self.owner_without_user_1,
            self.owner_without_user_2,
            self.student,
        ]
        for owner in still_connected:
            owner.refresh_from_db()
            self.assertTrue(
                AccountsUsers.objects.filter(
                    account=self.account, user_id=owner.user_id
                ).exists()
            )

        self.owner_with_user_1.refresh_from_db()  # removed user
        # no longer connected to account
        self.assertFalse(
            AccountsUsers.objects.filter(
                account=self.account, user_id=self.owner_with_user_1.user_id
            ).exists()
        )
        # still connected to org
        self.assertIn(
            self.owner_with_user_1.ownerid,
            Owner.objects.get(pk=self.org_2.pk).plan_activated_users,
        )
        # user object still exists, with no account connections
        self.assertIsNotNone(self.owner_with_user_1.user_id)
        self.assertFalse(
            AccountsUsers.objects.filter(user=self.owner_with_user_1.user).exists()
        )


class StripeBillingAdminTest(TestCase):
    def setUp(self):
        self.staff_user = UserFactory(is_staff=True)
        self.client.force_login(user=self.staff_user)
        admin_site = AdminSite()
        admin_site.register(StripeBilling)
        self.stripe_admin = StripeBillingAdmin(StripeBilling, admin_site)
        self.account = AccountFactory()
        self.obj = StripeBillingFactory(account=self.account)

    def test_account_widget(self):
        rf = RequestFactory()
        get_request = rf.get(f"/admin/codecov_auth/stripebilling/{self.obj.id}/change/")
        sample_input = {
            "change": True,
            "fields": [
                "id",
                "created_at",
                "updated_at",
                "account",
                "customer_id",
                "subscription_id",
                "is_active",
            ],
        }
        form = self.stripe_admin.get_form(
            request=get_request, obj=self.obj, **sample_input
        )
        # admin user cannot create, edit, or delete Account objects from the StripeBillingAdmin
        self.assertFalse(form.base_fields["account"].widget.can_add_related)
        self.assertFalse(form.base_fields["account"].widget.can_change_related)
        self.assertFalse(form.base_fields["account"].widget.can_delete_related)


class InvoiceBillingAdminTest(TestCase):
    def setUp(self):
        self.staff_user = UserFactory(is_staff=True)
        self.client.force_login(user=self.staff_user)
        admin_site = AdminSite()
        admin_site.register(InvoiceBilling)
        self.invoice_admin = InvoiceBillingAdmin(InvoiceBilling, admin_site)
        self.account = AccountFactory()
        self.obj = InvoiceBillingFactory(account=self.account)

    def test_account_widget(self):
        rf = RequestFactory()
        get_request = rf.get(
            f"/admin/codecov_auth/invoicebilling/{self.obj.id}/change/"
        )
        sample_input = {
            "change": True,
            "fields": [
                "id",
                "created_at",
                "updated_at",
                "account",
                "account_manager",
                "invoice_notes",
                "is_active",
            ],
        }
        form = self.invoice_admin.get_form(
            request=get_request, obj=self.obj, **sample_input
        )
        # admin user cannot create, edit, or delete Account objects from the InvoiceBillingAdmin
        self.assertFalse(form.base_fields["account"].widget.can_add_related)
        self.assertFalse(form.base_fields["account"].widget.can_change_related)
        self.assertFalse(form.base_fields["account"].widget.can_delete_related)
