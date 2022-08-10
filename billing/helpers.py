from django.conf import settings

from billing import constants
from codecov_auth.models import Owner


def on_enterprise_plan(owner: Owner) -> bool:
    return settings.IS_ENTERPRISE or (
        owner.plan in constants.ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS.keys()
    )
