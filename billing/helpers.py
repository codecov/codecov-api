import json
from typing import List, Union

from django.conf import settings
from django.contrib.auth.models import AnonymousUser

import services.sentry as sentry
from codecov_auth.models import Owner
from graphql_api.types import plan
from plan.constants import (
    ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS,
    FREE_PLAN_REPRESENTATIONS,
    PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS,
    SENTRY_PAID_USER_PLAN_REPRESENTATIONS,
)


def on_enterprise_plan(owner: Owner) -> bool:
    return settings.IS_ENTERPRISE or (
        owner.plan in ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS.keys()
    )


def available_plans(user: Union[Owner, AnonymousUser]) -> List[dict]:
    """
    Returns all plan representations available to the given owner.
    """
    # these are available to everyone
    plans = []
    # print("I'm here", FREE_PLAN_REPRESENTATIONS)
    # print("I'm here", FREE_PLAN_REPRESENTATIONS.values())
    # print("I'm here", FREE_PLAN_REPRESENTATIONS.values().toJSON())
    plans += list(FREE_PLAN_REPRESENTATIONS.values())
    plans += list(PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values())

    if user.is_authenticated and sentry.is_sentry_user(user):
        # these are only available to Sentry users
        plans += list(SENTRY_PAID_USER_PLAN_REPRESENTATIONS.values())

    # TODO: not sure if I need to add the trial plan here
    plans = [json.loads(plan.toJSON()) for plan in plans]
    print("aaa", plans)
    return plans
