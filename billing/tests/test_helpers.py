from django.test import TestCase, override_settings
from shared.django_apps.codecov_auth.tests.factories import PlanFactory, TierFactory
from shared.django_apps.core.tests.factories import OwnerFactory
from shared.plan.constants import (
    ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS,
    PlanName,
    TierName,
)

from billing.helpers import on_enterprise_plan


class HelpersTestCase(TestCase):
    @override_settings(IS_ENTERPRISE=True)
    def test_on_enterprise_plan_on_prem(self):
        owner = OwnerFactory()
        assert on_enterprise_plan(owner) == True

    def test_on_enterprise_plan_enterpise_cloud(self):
        enterprise_tier = TierFactory(tier_name=TierName.ENTERPRISE.value)
        PlanFactory(
            name=PlanName.ENTERPRISE_CLOUD_MONTHLY.value,
            tier=enterprise_tier,
            is_active=True,
        )
        PlanFactory(
            name=PlanName.ENTERPRISE_CLOUD_YEARLY.value,
            tier=enterprise_tier,
            is_active=True,
        )
        for plan in ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS.keys():
            owner = OwnerFactory(plan=plan)
            assert on_enterprise_plan(owner) == True

    def test_on_enterprise_plan_cloud(self):
        owner = OwnerFactory()
        assert on_enterprise_plan(owner) == False
