import enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from django.forms import ValidationError

from codecov_auth.models import Owner


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


class PlanNames(enum.Enum):
    FREE_PLAN_NAME = "users-free"
    GHM_PLAN_NAME = "users"
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

USER_PLAN_REPRESENTATIONS = {
    **FREE_PLAN_REPRESENTATIONS,
    **NON_PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS,
    **PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS,
    **SENTRY_PAID_USER_PLAN_REPRESENTATIONS,
    **GHM_PLAN_REPRESENTATION,
    **ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS,
}


class PlanService:
    def __init__(self, current_org: Owner):
        """
        Initializes a plan service object with a plan. The plan will be a trial plan
        if applicable

        Args:
            current_org (Owner): this is selected organization entry. This is not the user that is sending the request.

        Returns:
            No value
        """
        self.current_org = current_org
        self.plan = USER_PLAN_REPRESENTATIONS[self.current_org.plan]

    def start_trial(self) -> None:
        """
        Method that starts trial on an organization if the trial_start_date
        is not empty.

        Returns:
            No value

        Raises:
            ValidationError: if trial has already started
        """
        if self.trial_status != TrialStatus.NOT_STARTED:
            raise ValidationError("Cannot start an existing trial")
        start_date = datetime.utcnow()
        self.current_org.trial_start_date = start_date
        # TODO: make days here be the amount of days belonging to the plan
        self.current_org.trial_end_date = start_date + timedelta(
            days=TrialDaysAmount.CODECOV_SENTRY.value
        )
        self.current_org.save()

    def expire_trial_preemptively(self) -> None:
        """
        Method that expires a trial upon demand. Usually trials will be considered
        expired based on the 'trial_status' property above, but a user can decide to
        cause that expiration premptively

        Raises:
            ValidationError: if trial hasnt started

        Returns:
            No value
        """
        # I initially wanted to raise a validation error if there wasnt a start date/end date, but this will
        # be hard to apply for entries before this migration without start/end trial dates
        if self.current_org.trial_end_date is None:
            raise ValidationError("Cannot expire an unstarted trial")
        self.current_org.trial_end_date = datetime.utcnow()
        self.current_org.save()

    @property
    # TODO: should this account for if a plan is paid?
    def trial_status(self) -> TrialStatus:
        """
        Property that determines the trial status based on the trial_start_date and
        the trial_end_date.

        Returns:
            Any value from TrialStatus Enum
        """
        trial_start_date = self.current_org.trial_start_date
        trial_end_date = self.current_org.trial_end_date

        if trial_start_date is None and trial_end_date is None:
            # Scenario: A paid customer before the trial changes were introduced (they can never undergo trial for this org)
            # I have to comment this for now because it is currently affected by a Stripe webhook we wont be using in the future.
            # if self.current_org.stripe_customer_id:
            #     return TrialStatus.CANNOT_TRIAL
            # else:
            return TrialStatus.NOT_STARTED
        # Scenario: An paid customer before the trial changes were introduced (they can never undergo trial for this org)
        # This type of customer would have None for both the start and trial end date, but I was thinking, upon plan cancellation,
        # we could ad some logic that to set both their start and end date to the exact same value and represent a customer that
        # was never able to trial after they cancel. Not 100% sold here but I think it works.
        elif trial_start_date == trial_end_date and self.current_org.stripe_customer_id:
            return TrialStatus.CANNOT_TRIAL
        elif datetime.utcnow() > trial_end_date:
            return TrialStatus.EXPIRED
        else:
            return TrialStatus.ONGOING

    @property
    def trial_start_date(self) -> Optional[datetime]:
        return self.current_org.trial_start_date

    @property
    def trial_end_date(self) -> Optional[datetime]:
        return self.current_org.trial_end_date

    @property
    def marketing_name(self) -> PlanMarketingName:
        return self.plan.marketing_name

    @property
    def plan_name(self) -> PlanNames:
        return self.plan.value

    @property
    def billing_rate(self) -> Optional[PlanBillingRate]:
        return self.plan.billing_rate

    @property
    def base_unit_price(self) -> PlanPrice:
        return self.plan.base_unit_price

    @property
    def benefits(self) -> List[str]:
        return self.plan.benefits

    @property
    def monthly_uploads_limit(self) -> Optional[MonthlyUploadLimits]:
        """
        Property that returns monthly uploads limit based on your trial status

        Returns:
            Optional number of uploads
        """
        if self.trial_status == TrialStatus.ONGOING:
            return None
        return self.plan.monthly_uploads_limit

    @property
    def trial_total_days(self) -> Optional[TrialDaysAmount]:
        return self.plan.trial_days
