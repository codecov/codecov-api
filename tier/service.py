from functools import cached_property

from plan.constants import (
    BASIC_TIER_PLAN_NAMES,
    ENTERPRISE_TIER_PLAN_NAMES,
    LITE_TIER_PLAN_NAMES,
    PRO_TIER_PLAN_NAMES,
    USER_PLAN_REPRESENTATIONS,
    PlanName,
)
from tier.constants import TierName


class TierService:
    def __init__(self, plan_name: PlanName):
        # TODO: Get rid of the OR condition; lite plans should be part of the user_plan_representation
        # object, we just don't know what values it will have so leaving it as is for now
        if (
            plan_name not in USER_PLAN_REPRESENTATIONS
            and plan_name not in LITE_TIER_PLAN_NAMES
        ):
            raise ValueError("Unsupported plan")
        self.plan_name = plan_name

    @cached_property
    def _is_pro_tier(self) -> bool:
        return self.plan_name in PRO_TIER_PLAN_NAMES

    @cached_property
    def _is_lite_tier(self) -> bool:
        return self.plan_name in LITE_TIER_PLAN_NAMES

    @cached_property
    def _is_basic_tier(self) -> bool:
        return self.plan_name in BASIC_TIER_PLAN_NAMES

    @cached_property
    def _is_enterprise_tier(self) -> bool:
        return self.plan_name in ENTERPRISE_TIER_PLAN_NAMES

    @property
    def tier(self) -> TierName:
        if self._is_enterprise_tier:
            return TierName.ENTERPRISE.value
        if self._is_pro_tier:
            return TierName.PRO.value
        if self._is_lite_tier:
            return TierName.LITE.value
        if self._is_basic_tier:
            return TierName.BASIC.value
        return TierName.BASIC.value
