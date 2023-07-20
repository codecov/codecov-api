import json
from typing import List, Optional

from django.conf import settings

import services.sentry as sentry
from codecov_auth.models import Owner
from plan.constants import (
    ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS,
    FREE_PLAN_REPRESENTATIONS,
    PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS,
    SENTRY_PAID_USER_PLAN_REPRESENTATIONS,
    PlanData,
)


def on_enterprise_plan(owner: Owner) -> bool:
    return settings.IS_ENTERPRISE or (
        owner.plan in ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS.keys()
    )


def available_plans(owner: Optional[Owner]) -> List[dict]:
    """
    Returns all plan representations available to the given owner.
    """
    # these are available to everyone
    plans: List[PlanData] = []
    plans += list(FREE_PLAN_REPRESENTATIONS.values())
    plans += list(PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values())

    if owner and sentry.is_sentry_user(owner):
        # these are only available to Sentry users
        plans += list(SENTRY_PAID_USER_PLAN_REPRESENTATIONS.values())

    # TODO: not sure if I need to add the trial plan here
    plans = [json.loads(plan.toJSON()) for plan in plans]
    return plans
