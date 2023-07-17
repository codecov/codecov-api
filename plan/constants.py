import enum
import json
from dataclasses import dataclass
from typing import List, Optional


class MonthlyUploadLimits(enum.Enum):
    CODECOV_BASIC_PLAN = 250


class TrialDaysAmount(enum.Enum):
    CODECOV_SENTRY = 14


class PlanMarketingName(enum.Enum):
    CODECOV_PRO = "Pro Team"
    SENTRY_PRO = "Pro Team for Sentry"
    ENTERPRISE_CLOUD = "Enterprise Cloud"
    GITHUB_MARKETPLACE = "Github Marketplace"
    FREE = "Developer"
    BASIC = "Developer"
    TRIAL = "Developer"


class PlanNames(enum.Enum):
    GHM_PLAN_NAME = "users"
    FREE_PLAN_NAME = "users-free"
    TRIAL_PLAN_NAME = "users-trial"
    BASIC_PLAN_NAME = "users-basic"
    CODECOV_PRO_MONTHLY_LEGACY = "users-inappm"
    CODECOV_PRO_YEARLY_LEGACY = "users-inappy"
    CODECOV_PRO_MONTHLY = "users-pr-inappm"
    CODECOV_PRO_YEARLY = "users-pr-inappy"
    SENTRY_MONTHLY = "users-sentrym"
    SENTRY_YEARLY = "users-sentryy"
    ENTERPRISE_CLOUD_MONTHLY = "users-enterprisem"
    ENTERPRISE_CLOUD_YEARLY = "users-enterprisey"


class PlanBillingRate(enum.Enum):
    MONTHLY = "monthly"
    YEARLY = "annually"


class PlanPrice(enum.Enum):
    MONTHLY = 12
    YEARLY = 10
    CODECOV_FREE = 0
    CODECOV_BASIC = 0
    CODECOV_TRIAL = 0
    GHM_PRICE = 12


class TrialStatus(enum.Enum):
    NOT_STARTED = "not_started"
    ONGOING = "ongoing"
    EXPIRED = "expired"
    CANNOT_TRIAL = "cannot_trial"


@dataclass(repr=False)
class PlanData:
    """
    Dataclass that represents plan related information
    """

    marketing_name: PlanMarketingName
    value: PlanNames
    billing_rate: Optional[PlanBillingRate]
    base_unit_price: PlanPrice
    benefits: List[str]
    monthly_uploads_limit: Optional[MonthlyUploadLimits]
    trial_days: Optional[TrialDaysAmount]

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__)


NON_PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS = {
    PlanNames.CODECOV_PRO_MONTHLY_LEGACY.value: PlanData(
        marketing_name=PlanMarketingName.CODECOV_PRO.value,
        value=PlanNames.CODECOV_PRO_MONTHLY_LEGACY.value,
        billing_rate=PlanBillingRate.MONTHLY.value,
        base_unit_price=PlanPrice.MONTHLY.value,
        benefits=[
            "Configurable # of users",
            "Unlimited public repositories",
            "Unlimited private repositories",
            "Priority Support",
        ],
        monthly_uploads_limit=None,
        trial_days=None,
    ),
    PlanNames.CODECOV_PRO_YEARLY_LEGACY.value: PlanData(
        marketing_name=PlanMarketingName.CODECOV_PRO.value,
        value=PlanNames.CODECOV_PRO_YEARLY_LEGACY.value,
        billing_rate=PlanBillingRate.YEARLY.value,
        base_unit_price=PlanPrice.YEARLY.value,
        benefits=[
            "Configurable # of users",
            "Unlimited public repositories",
            "Unlimited private repositories",
            "Priority Support",
        ],
        monthly_uploads_limit=None,
        trial_days=None,
    ),
}


PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS = {
    PlanNames.CODECOV_PRO_MONTHLY.value: PlanData(
        marketing_name=PlanMarketingName.CODECOV_PRO.value,
        value=PlanNames.CODECOV_PRO_MONTHLY.value,
        billing_rate=PlanBillingRate.MONTHLY.value,
        base_unit_price=PlanPrice.MONTHLY.value,
        benefits=[
            "Configurable # of users",
            "Unlimited public repositories",
            "Unlimited private repositories",
            "Priority Support",
        ],
        monthly_uploads_limit=None,
        trial_days=None,
    ),
    PlanNames.CODECOV_PRO_YEARLY.value: PlanData(
        marketing_name=PlanMarketingName.CODECOV_PRO.value,
        value=PlanNames.CODECOV_PRO_YEARLY.value,
        billing_rate=PlanBillingRate.YEARLY.value,
        base_unit_price=PlanPrice.YEARLY.value,
        benefits=[
            "Configurable # of users",
            "Unlimited public repositories",
            "Unlimited private repositories",
            "Priority Support",
        ],
        monthly_uploads_limit=None,
        trial_days=None,
    ),
}

SENTRY_PAID_USER_PLAN_REPRESENTATIONS = {
    PlanNames.SENTRY_MONTHLY.value: PlanData(
        marketing_name=PlanMarketingName.SENTRY_PRO.value,
        value=PlanNames.SENTRY_MONTHLY.value,
        billing_rate=PlanBillingRate.MONTHLY.value,
        base_unit_price=PlanPrice.MONTHLY.value,
        benefits=[
            "Includes 5 seats",
            "$12 per additional seat",
            "Unlimited public repositories",
            "Unlimited private repositories",
            "Priority Support",
        ],
        trial_days=TrialDaysAmount.CODECOV_SENTRY.value,
        monthly_uploads_limit=None,
    ),
    PlanNames.SENTRY_YEARLY.value: PlanData(
        marketing_name=PlanMarketingName.SENTRY_PRO.value,
        value=PlanNames.SENTRY_YEARLY.value,
        billing_rate=PlanBillingRate.YEARLY.value,
        base_unit_price=PlanPrice.YEARLY.value,
        benefits=[
            "Includes 5 seats",
            "$10 per additional seat",
            "Unlimited public repositories",
            "Unlimited private repositories",
            "Priority Support",
        ],
        trial_days=TrialDaysAmount.CODECOV_SENTRY.value,
        monthly_uploads_limit=None,
    ),
}

# TODO: Update these values
ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS = {
    PlanNames.ENTERPRISE_CLOUD_MONTHLY.value: PlanData(
        marketing_name=PlanMarketingName.ENTERPRISE_CLOUD.value,
        value=PlanNames.ENTERPRISE_CLOUD_MONTHLY.value,
        billing_rate=PlanBillingRate.MONTHLY.value,
        base_unit_price=PlanPrice.MONTHLY.value,
        benefits=[
            "Configurable # of users",
            "Unlimited public repositories",
            "Unlimited private repositories",
            "Priority Support",
        ],
        trial_days=None,
        monthly_uploads_limit=None,
    ),
    PlanNames.ENTERPRISE_CLOUD_YEARLY.value: PlanData(
        marketing_name=PlanMarketingName.ENTERPRISE_CLOUD.value,
        value=PlanNames.ENTERPRISE_CLOUD_YEARLY.value,
        billing_rate=PlanBillingRate.YEARLY.value,
        base_unit_price=PlanPrice.YEARLY.value,
        benefits=[
            "Configurable # of users",
            "Unlimited public repositories",
            "Unlimited private repositories",
            "Priority Support",
        ],
        trial_days=None,
        monthly_uploads_limit=None,
    ),
}

GHM_PLAN_REPRESENTATION = {
    PlanNames.GHM_PLAN_NAME.value: PlanData(
        marketing_name=PlanMarketingName.GITHUB_MARKETPLACE.value,
        value=PlanNames.GHM_PLAN_NAME.value,
        billing_rate=None,
        base_unit_price=PlanPrice.GHM_PRICE.value,
        benefits=[
            "Configurable # of users",
            "Unlimited public repositories",
            "Unlimited private repositories",
        ],
        trial_days=None,
        monthly_uploads_limit=None,
    )
}

FREE_PLAN_REPRESENTATIONS = {
    PlanNames.FREE_PLAN_NAME.value: PlanData(
        marketing_name=PlanMarketingName.FREE.value,
        value=PlanNames.FREE_PLAN_NAME.value,
        billing_rate=None,
        base_unit_price=PlanPrice.CODECOV_FREE.value,
        benefits=[
            "Up to 1 user",
            "Unlimited public repositories",
            "Unlimited private repositories",
        ],
        trial_days=None,
        monthly_uploads_limit=None,
    ),
    PlanNames.BASIC_PLAN_NAME.value: PlanData(
        marketing_name=PlanMarketingName.BASIC.value,
        value=PlanNames.BASIC_PLAN_NAME.value,
        billing_rate=None,
        base_unit_price=PlanPrice.CODECOV_BASIC.value,
        benefits=[
            "Up to 1 user",
            "Unlimited public repositories",
            "Unlimited private repositories",
        ],
        monthly_uploads_limit=MonthlyUploadLimits.CODECOV_BASIC_PLAN.value,
        trial_days=None,
    ),
}

TRIAL_PLAN_REPRESENTATION = {
    PlanNames.TRIAL_PLAN_NAME.value: PlanData(
        marketing_name=PlanMarketingName.TRIAL.value,
        value=PlanNames.TRIAL_PLAN_NAME.value,
        billing_rate=None,
        base_unit_price=PlanPrice.CODECOV_TRIAL.value,
        benefits=[
            "Configurable # of users",
            "Unlimited public repositories",
            "Unlimited private repositories",
            "Priority Support",
        ],
        trial_days=None,
        monthly_uploads_limit=None,
    ),
}

PRO_PLANS = {
    **PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS,
    **SENTRY_PAID_USER_PLAN_REPRESENTATIONS,
    **ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS,
}

TRIAL_PLANS = {**TRIAL_PLAN_REPRESENTATION}

USER_PLAN_REPRESENTATIONS = {
    **FREE_PLAN_REPRESENTATIONS,
    **NON_PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS,
    **GHM_PLAN_REPRESENTATION,
    **PRO_PLANS,
    **TRIAL_PLANS,
}
