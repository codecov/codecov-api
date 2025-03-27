from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from shared.django_apps.codecov_auth.models import (
    Account,
    AccountsUsers,
    InvoiceBilling,
    StripeBilling,
)
from shared.django_apps.codecov_auth.tests.factories import (
    AccountFactory,
    InvoiceBillingFactory,
    OrganizationLevelTokenFactory,
    OwnerFactory,
    PlanFactory,
    SentryUserFactory,
    SessionFactory,
    StripeBillingFactory,
    TierFactory,
    UserFactory,
)
from shared.django_apps.core.tests.factories import PullFactory, RepositoryFactory
from shared.plan.constants import (
    DEFAULT_FREE_PLAN,
    PlanName,
)

from billing.helpers import mock_all_plans_and_tiers
from codecov.commands.exceptions import ValidationError
from codecov_auth.admin import (
    AccountAdmin,
    InvoiceBillingAdmin,
    OrgUploadTokenInline,
    OwnerAdmin,
    StripeBillingAdmin,
    UserAdmin,
    find_and_remove_stale_users,
)
from codecov_auth.models import (
    OrganizationLevelToken,
    Owner,
    Plan,
    SentryUser,
    Tier,
    User,
)
from core.models import Pull


class OwnerAdminTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_all_plans_and_tiers()

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
        owner_to_impersonate = OwnerFactory(service="bitbucket", plan=DEFAULT_FREE_PLAN)
        other_owner = OwnerFactory(plan=DEFAULT_FREE_PLAN)

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

 
