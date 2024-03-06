import logging
from datetime import datetime, timedelta
from typing import List, Optional

from codecov.commands.exceptions import ValidationError
from codecov_auth.models import Owner
from plan.constants import (
    BASIC_PLAN,
    FREE_PLAN,
    FREE_PLAN_REPRESENTATIONS,
    PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS,
    SENTRY_PAID_USER_PLAN_REPRESENTATIONS,
    TEAM_PLAN_MAX_USERS,
    TEAM_PLAN_REPRESENTATIONS,
    TRIAL_PLAN_REPRESENTATION,
    TRIAL_PLAN_SEATS,
    USER_PLAN_REPRESENTATIONS,
    PlanData,
    PlanName,
    TrialDaysAmount,
    TrialStatus,
)
from services import sentry

log = logging.getLogger(__name__)


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

    def current_org(self) -> Owner:
        return self.current_org

    def set_default_plan_data(self) -> None:
        log.info(f"Setting plan to users-basic for owner {self.current_org.ownerid}")
        self.current_org.plan = PlanName.BASIC_PLAN_NAME.value
        self.current_org.plan_activated_users = None
        self.current_org.plan_user_count = 1
        self.current_org.stripe_subscription_id = None
        self.current_org.save()

    @property
    def plan_name(self) -> str:
        return self.plan_data.value

    @property
    def plan_user_count(self) -> int:
        return self.current_org.plan_user_count

    @property
    def plan_activated_users(self) -> Optional[List[int]]:
        return self.current_org.plan_activated_users

    @property
    def pretrial_users_count(self) -> int:
        return self.current_org.pretrial_users_count or 1

    @property
    def marketing_name(self) -> str:
        return self.plan_data.marketing_name

    @property
    def billing_rate(self) -> Optional[str]:
        return self.plan_data.billing_rate

    @property
    def base_unit_price(self) -> int:
        return self.plan_data.base_unit_price

    @property
    def benefits(self) -> List[str]:
        return self.plan_data.benefits

    @property
    def monthly_uploads_limit(self) -> Optional[int]:
        """
        Property that returns monthly uploads limit based on your trial status

        Returns:
            Optional number of monthly uploads
        """
        return self.plan_data.monthly_uploads_limit

    @property
    def tier_name(self) -> str:
        return self.plan_data.tier_name

    def available_plans(self, owner: Owner) -> List[PlanData]:
        """
        Returns the available plans for an owner and an organization

        Args:
            current_owner (Owner): this is the user that is sending the request.

        Returns:
            No value
        """
        available_plans = []
        available_plans.append(BASIC_PLAN)

        if self.plan_name == FREE_PLAN.value:
            available_plans.append(FREE_PLAN)

        available_plans += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()

        if owner and sentry.is_sentry_user(owner=owner):
            available_plans += SENTRY_PAID_USER_PLAN_REPRESENTATIONS.values()

            # If number of activated users is less than or equal to TEAM_PLAN_MAX_USERS
        if (
            self.plan_activated_users is None
            or len(self.plan_activated_users) <= TEAM_PLAN_MAX_USERS
        ):
            available_plans += TEAM_PLAN_REPRESENTATIONS.values()

        return available_plans

    def _start_trial_helper(
        self,
        current_owner: Owner,
        end_date: datetime = None,
        is_extension: bool = False,
    ) -> None:
        start_date = datetime.utcnow()

        # When they are not extending a trial, have to setup all the default values
        if not is_extension:
            self.current_org.trial_start_date = start_date
            self.current_org.trial_status = TrialStatus.ONGOING.value
            self.current_org.plan = PlanName.TRIAL_PLAN_NAME.value
            self.current_org.pretrial_users_count = self.current_org.plan_user_count
            self.current_org.plan_user_count = TRIAL_PLAN_SEATS
            self.current_org.plan_auto_activate = True

        if end_date is None:
            self.current_org.trial_end_date = start_date + timedelta(
                days=TrialDaysAmount.CODECOV_SENTRY.value
            )
        else:
            self.current_org.trial_end_date = end_date
        self.current_org.trial_fired_by = current_owner.ownerid
        self.current_org.save()

    # Trial Data
    def start_trial(self, current_owner: Owner) -> None:
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

        self._start_trial_helper(current_owner)

    def start_trial_manually(self, current_owner: Owner, end_date: datetime) -> None:
        """
        Method that start trial immediately and ends at a predefined date for an organization
        Used by administrators to manually start and extend trials

        Returns:
            No value
        """
        # Start a new trial plan for free users currently not on trial
        if self.plan_name in FREE_PLAN_REPRESENTATIONS:
            self._start_trial_helper(current_owner, end_date, is_extension=False)
        # Extend an existing trial plan for users currently on trial
        elif self.plan_name in TRIAL_PLAN_REPRESENTATION:
            self._start_trial_helper(current_owner, end_date, is_extension=True)
        # Paying users cannot start a trial
        else:
            raise ValidationError("Cannot trial from a paid plan")

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
    def trial_total_days(self) -> Optional[int]:
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
