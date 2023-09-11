import logging
from datetime import datetime, timedelta
from typing import List, Optional

from codecov.commands.exceptions import ValidationError
from codecov_auth.models import Owner
from plan.constants import (
    FREE_PLAN_REPRESENTATIONS,
    TRIAL_PLAN_SEATS,
    USER_PLAN_REPRESENTATIONS,
    MonthlyUploadLimits,
    PlanBillingRate,
    PlanMarketingName,
    PlanName,
    PlanPrice,
    TrialDaysAmount,
    TrialStatus,
)
from services.segment import SegmentService

log = logging.getLogger(__name__)


# TODO: Consider moving some of these methods to the billing directory as they overlap billing functionality
class PlanService:
    notifier_service = SegmentService()

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
        return self.plan_data.value

    @property
    def plan_user_count(self) -> int:
        return self.current_org.plan_user_count

    @property
    def pretrial_users_count(self) -> int:
        return self.current_org.pretrial_users_count or 1

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
        if self.trial_status != TrialStatus.NOT_STARTED.value:
            raise ValidationError("Cannot start an existing trial")
        if self.plan_name not in FREE_PLAN_REPRESENTATIONS:
            raise ValidationError("Cannot trial from a paid plan")
        start_date = datetime.utcnow()
        self.current_org.trial_start_date = start_date
        self.current_org.trial_end_date = start_date + timedelta(
            days=TrialDaysAmount.CODECOV_SENTRY.value
        )
        self.current_org.trial_status = TrialStatus.ONGOING.value
        self.current_org.plan = PlanName.TRIAL_PLAN_NAME.value
        self.current_org.pretrial_users_count = self.current_org.plan_user_count
        self.current_org.plan_user_count = TRIAL_PLAN_SEATS
        self.current_org.plan_auto_activate = True
        self.current_org.save()

        self.notifier_service.trial_started(
            org_ownerid=self.current_org.ownerid,
            trial_details={
                "trial_plan_name": self.current_org.plan,
                "trial_start_date": self.current_org.trial_start_date,
                "trial_end_date": self.current_org.trial_end_date,
            },
        )

    def cancel_trial(self) -> None:
        if not self.is_org_trialing:
            raise ValidationError("Cannot cancel a trial that is not ongoing")
        now = datetime.utcnow()
        self.current_org.trial_status = TrialStatus.EXPIRED.value
        self.current_org.trial_end_date = now
        self.set_default_plan_data()

    def expire_trial_when_upgrading(self) -> None:
        """
        Method that expires trial on an organization based on it's current trial status.


        Returns:
            No value
        """
        if self.trial_status == TrialStatus.EXPIRED.value:
            return
        if self.trial_status != TrialStatus.CANNOT_TRIAL.value:
            # Not adjusting the trial start/end dates here as some customers can
            # directly purchase a plan without trialing first
            self.current_org.trial_status = TrialStatus.EXPIRED.value
            self.current_org.plan_activated_users = None
            self.current_org.plan_user_count = (
                self.current_org.pretrial_users_count or 1
            )
            self.current_org.trial_end_date = datetime.utcnow()

            self.current_org.save()
            self.notifier_service.trial_ended(
                org_ownerid=self.current_org.ownerid,
                trial_details={
                    "trial_plan_name": self.current_org.plan,
                    "trial_start_date": self.current_org.trial_start_date,
                    "trial_end_date": self.current_org.trial_end_date,
                },
            )

    @property
    def trial_status(self) -> TrialStatus:
        return self.current_org.trial_status

    @property
    def trial_start_date(self) -> Optional[datetime]:
        return self.current_org.trial_start_date

    @property
    def trial_end_date(self) -> Optional[datetime]:
        return self.current_org.trial_end_date

    @property
    def trial_total_days(self) -> Optional[TrialDaysAmount]:
        return self.plan_data.trial_days

    @property
    def is_org_trialing(self) -> bool:
        return (
            self.trial_status == TrialStatus.ONGOING.value
            and self.plan_name == PlanName.TRIAL_PLAN_NAME.value
        )

    @property
    def has_trial_dates(self) -> bool:
        return bool(self.trial_start_date and self.trial_end_date)
