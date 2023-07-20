from typing import List, Optional

from django.conf import settings
from django.contrib.auth.models import AnonymousUser

import services.sentry as sentry
from billing import constants
from codecov_auth.models import Owner


def on_enterprise_plan(owner: Owner) -> bool:
    return settings.IS_ENTERPRISE or (
        owner.plan in constants.ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS.keys()
    )


def available_plans(owner: Optional[Owner]) -> List[dict]:
    """
    Returns all plan representations available to the given owner.
    """
    # these are available to everyone
    plans = []
    plans += list(constants.FREE_PLAN_REPRESENTATIONS.values())
    plans += list(constants.PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values())

    if owner and sentry.is_sentry_user(owner):
        # these are only available to Sentry users
        plans += list(constants.SENTRY_PAID_USER_PLAN_REPRESENTATIONS.values())

    return plans
