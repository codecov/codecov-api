import logging
from datetime import datetime, timedelta
from typing import List, Optional

from codecov.commands.exceptions import ValidationError
from codecov_auth.models import Owner
from plan.constants import (
    USER_PLAN_REPRESENTATIONS,
    MonthlyUploadLimits,
    PlanBillingRate,
    PlanMarketingName,
    PlanName,
    PlanPrice,
    TrialDaysAmount,
    TrialStatus,
)

log = logging.getLogger(__name__)


# TODO: Change notifier_service type to Abstract Class for a NotifierService rather than SegmentService
# TODO: Consider moving some of these methods to the billing directory as they overlap billing functionality
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
        # TODO: how to account for super archaic plan names like "v4-10y"
        if self.current_org.plan not in USER_PLAN_REPRESENTATIONS:
            raise ValueError("Unsupported plan")
        else:
            self.plan_data = USER_PLAN_REPRESENTATIONS[self.current_org.plan]

    def update_plan(self, name: PlanName, user_count: int) -> None:
        if name not in USER_PLAN_REPRESENTATIONS:
            raise ValueError("Unsupported plan")
        self.current_org.plan = name
        self.current_org.plan_user_count = user_count
        self.plan_data = USER_PLAN_REPRESENTATIONS[self.current_org.plan]
        self.current_org.save()

    def set_default_plan_data(self) -> None:
        log.info(f"Setting plan to users-basic for owner {self.current_org.ownerid}")
        self.current_org.plan = PlanName.BASIC_PLAN_NAME.value
        self.current_org.plan_activated_users = None
        self.current_org.plan_user_count = 1
        self.current_org.stripe_subscription_id = None
        self.current_org.save()

    @property
    def plan_name(self) -> PlanName:
        return self.current_org.plan

    @property
    def plan_user_count(self) -> int:
        return self.current_org.plan_user_count

    @property
    def marketing_name(self) -> PlanMarketingName:
        return self.plan_data.marketing_name

    @property
    def billing_rate(self) -> Optional[PlanBillingRate]:
        return self.plan_data.billing_rate

    @property
    def base_unit_price(self) -> PlanPrice:
        return self.plan_data.base_unit_price

    @property
    def benefits(self) -> List[str]:
        return self.plan_data.benefits

    @property
    def monthly_uploads_limit(self) -> Optional[MonthlyUploadLimits]:
        """
        Property that returns monthly uploads limit based on your trial status

        Returns:
            Optional number of monthly uploads
        """
        return self.plan_data.monthly_uploads_limit

    # Trial Data
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
        self.current_org.trial_end_date = start_date + timedelta(
            days=TrialDaysAmount.CODECOV_SENTRY.value
        )
        self.current_org.plan_auto_activate = True
        self.current_org.save()
        # TODO: uncomment these for ticket adding trial logic
        # self.current_org.plan = PlanName.TRIAL_PLAN_NAME.value
        # self.current_org.trial_status = TrialStatus.ONGOING
        # notifier_service.trial_started(
        #     org_ownerid=self.current_org.ownerid,
        #     trial_details={
        #         "trial_plan_name": self.current_org.plan,
        #         "trial_start_date": self.current_org.trial_start_date,
        #         "trial_end_date": self.current_org.trial_end_date,
        #     },
        # )

    def cancel_trial(self) -> None:
        print("trial_status_val", self.trial_status)
        # TODO: change this to TrialStatus.ONGOING.value in CODE-3605-add-trial-logic
        if self.trial_status != TrialStatus.ONGOING:
            raise ValidationError("Cannot cancel a trial that is not ongoing")
        now = datetime.utcnow()
        self.current_org.trial_status = TrialStatus.EXPIRED.value
        self.current_org.trial_end_date = now
        self.set_default_plan_data()

    def expire_trial(self) -> None:
        if (
            self.trial_status == TrialStatus.NOT_STARTED
            or self.trial_status == TrialStatus.ONGOING
        ):
            self.current_org.trial_end_date = datetime.utcnow()
            # self.current_org.trial_status = TrialStatus.EXPIRED
            self.current_org.save()
            # notifier_service.trial_ended(
            #     org_ownerid=self.current_org.ownerid,
            #     trial_details={
            #         "trial_plan_name": self.current_org.plan,
            #         "trial_start_date": self.current_org.trial_start_date,
            #         "trial_end_date": self.current_org.trial_end_date,
            #     },
            # )

    @property
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
    def trial_total_days(self) -> Optional[TrialDaysAmount]:
        return self.plan_data.trial_days
