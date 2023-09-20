from yarl import cached_property
from plan.constants import PRO_PLAN_NAMES, PlanName


class Features:
    def __init__(self, plan_name: PlanName):
        self.plan_name = plan_name

    @cached_property
    def _is_pro_team_feature(self) -> bool:
        return self.plan_name in PRO_PLAN_NAMES

    @property
    def has_flags_timeseries_flags(self) -> bool:
        return self._is_pro_team_feature
