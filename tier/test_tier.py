from django.test import TestCase

from plan.constants import (
    BASIC_TIER_PLAN_NAMES,
    ENTERPRISE_TIER_PLAN_NAMES,
    LITE_TIER_PLAN_NAMES,
    PRO_TIER_PLAN_NAMES,
)
from tier.constants import TierName
from tier.service import TierService


class PlanServiceTests(TestCase):
    def test_plan_is_enterprise_tier(self):
        for plan_name in ENTERPRISE_TIER_PLAN_NAMES:
            tier_service = TierService(plan_name=plan_name)
            assert tier_service.tier == TierName.ENTERPRISE

    def test_plan_is_pro_tier(self):
        for plan_name in PRO_TIER_PLAN_NAMES:
            tier_service = TierService(plan_name=plan_name)
            assert tier_service.tier == TierName.PRO

    def test_plan_is_lite_tier(self):
        for plan_name in LITE_TIER_PLAN_NAMES:
            tier_service = TierService(plan_name=plan_name)
            assert tier_service.tier == TierName.LITE

    def test_plan_is_basic_tier(self):
        for plan_name in BASIC_TIER_PLAN_NAMES:
            tier_service = TierService(plan_name=plan_name)
            assert tier_service.tier == TierName.BASIC

    def test_plan_not_belonging_to_tier_plans(self):
        with self.assertRaises(ValueError) as e:
            TierService(plan_name=None)
