from django.conf import settings

from codecov_auth.models import Owner
from plan.constants import ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS


def on_enterprise_plan(owner: Owner) -> bool:
    return settings.IS_ENTERPRISE or (
        owner.plan in ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS.keys()
    )
