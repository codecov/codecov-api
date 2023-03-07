from typing import List

from django.conf import settings

import services.sentry as sentry
from billing import constants
from codecov_auth.models import Owner


def on_enterprise_plan(owner: Owner) -> bool:
    return settings.IS_ENTERPRISE or (
        owner.plan in constants.ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS.keys()
    )


def available_plans(user: Owner) -> List[dict]:
    """
    Returns all plan representations available to the given owner.
    """
    # these are available to everyone
    plans = [val for key, val in constants.CURRENTLY_OFFERED_PLANS.items()]

    if sentry.is_sentry_user(user):
        # these are only available to Sentry users
        plans += [
            val for key, val in constants.SENTRY_PAID_USER_PLAN_REPRESENTATIONS.items()
        ]

    return plans
