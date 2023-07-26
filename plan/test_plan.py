from datetime import datetime, timedelta

from django.test import TestCase
from freezegun import freeze_time

from codecov.commands.exceptions import ValidationError
from codecov_auth.tests.factories import OwnerFactory
from plan.constants import (
    FREE_PLAN_REPRESENTATIONS,
    TRIAL_PLAN_REPRESENTATION,
    TRIAL_PLAN_SEATS,
    PlanName,
    TrialDaysAmount,
    TrialStatus,
)
from plan.service import PlanService


@freeze_time("2023-06-19")
class PlanServiceTests(TestCase):
    def test_plan_service_trial_status_not_started(self):
        current_org = OwnerFactory(plan=PlanName.BASIC_PLAN_NAME.value)
        plan_service = PlanService(current_org=current_org)

        assert plan_service.trial_status == TrialStatus.NOT_STARTED.value

    def test_plan_service_trial_status_expired(self):
        trial_start_date = datetime.utcnow()
        trial_end_date_expired = trial_start_date - timedelta(days=1)
        current_org = OwnerFactory(
            plan=PlanName.BASIC_PLAN_NAME.value,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date_expired,
            trial_status=TrialStatus.EXPIRED.value,
        )
        plan_service = PlanService(current_org=current_org)

        assert plan_service.trial_status == TrialStatus.EXPIRED.value

    def test_plan_service_trial_status_ongoing(self):
        trial_start_date = datetime.utcnow()
        trial_end_date_ongoing = trial_start_date + timedelta(days=5)
        current_org = OwnerFactory(
            plan=PlanName.BASIC_PLAN_NAME.value,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date_ongoing,
            trial_status=TrialStatus.ONGOING.value,
        )
        plan_service = PlanService(current_org=current_org)

        assert plan_service.trial_status == TrialStatus.ONGOING.value

    def test_plan_service_expire_trial_when_upgrading_successful_if_trial_is_ongoing(
        self,
    ):
        trial_start_date = datetime.utcnow()
        trial_end_date_ongoing = trial_start_date + timedelta(days=5)
        current_org_with_ongoing_trial = OwnerFactory(
            plan=PlanName.BASIC_PLAN_NAME.value,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date_ongoing,
            trial_status=TrialStatus.ONGOING.value,
        )
        plan_service = PlanService(current_org=current_org_with_ongoing_trial)
        plan_service.expire_trial_when_upgrading()
        assert current_org_with_ongoing_trial.trial_status == TrialStatus.EXPIRED.value
        assert current_org_with_ongoing_trial.plan_activated_users == None
        assert current_org_with_ongoing_trial.plan_user_count == 1

    def test_plan_service_start_trial_errors_if_status_is_not_not_started(self):
        trial_start_date = datetime.utcnow()
        trial_end_date = trial_start_date + timedelta(
            days=TrialDaysAmount.CODECOV_SENTRY.value
        )
        current_org = OwnerFactory(
            plan=PlanName.BASIC_PLAN_NAME.value,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
            trial_status=TrialStatus.ONGOING.value,
        )
        plan_service = PlanService(current_org=current_org)

        with self.assertRaises(ValidationError) as e:
            plan_service.start_trial()

    def test_plan_service_start_trial_succeeds_if_trial_has_not_started(self):
        trial_start_date = None
        trial_end_date = None
        current_org = OwnerFactory(
            plan=PlanName.BASIC_PLAN_NAME.value,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
            trial_status=TrialStatus.NOT_STARTED.value,
        )
        plan_service = PlanService(current_org=current_org)

        plan_service.start_trial()
        assert current_org.trial_start_date == datetime.utcnow()
        assert current_org.trial_end_date == datetime.utcnow() + timedelta(
            days=TrialDaysAmount.CODECOV_SENTRY.value
        )
        assert current_org.trial_status == TrialStatus.ONGOING.value
        assert current_org.plan == PlanName.TRIAL_PLAN_NAME.value
        assert current_org.plan_user_count == TRIAL_PLAN_SEATS
        assert current_org.plan_auto_activate == True

    def test_plan_service_returns_plan_data_for_non_trial_basic_plan(self):
        trial_start_date = None
        trial_end_date = None
        current_org = OwnerFactory(
            plan=PlanName.BASIC_PLAN_NAME.value,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
        )
        plan_service = PlanService(current_org=current_org)

        basic_plan = FREE_PLAN_REPRESENTATIONS[PlanName.BASIC_PLAN_NAME.value]
        assert plan_service.trial_status == TrialStatus.NOT_STARTED.value
        assert plan_service.marketing_name == basic_plan.marketing_name
        assert plan_service.plan_name == basic_plan.value
        assert plan_service.billing_rate == basic_plan.billing_rate
        assert plan_service.base_unit_price == basic_plan.base_unit_price
        assert plan_service.benefits == basic_plan.benefits
        assert (
            plan_service.monthly_uploads_limit == basic_plan.monthly_uploads_limit
        )  # should be 250
        assert (
            plan_service.monthly_uploads_limit == 250
        )  # should be 250 since not trialing
        assert plan_service.trial_total_days == basic_plan.trial_days

    def test_plan_service_returns_plan_data_for_trialing_user_trial_plan(self):
        trial_start_date = datetime.utcnow()
        trial_end_date = datetime.utcnow() + timedelta(
            days=TrialDaysAmount.CODECOV_SENTRY.value
        )
        current_org = OwnerFactory(
            plan=PlanName.TRIAL_PLAN_NAME.value,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
            trial_status=TrialStatus.ONGOING.value,
        )
        plan_service = PlanService(current_org=current_org)

        trial_plan = TRIAL_PLAN_REPRESENTATION[PlanName.TRIAL_PLAN_NAME.value]
        assert plan_service.trial_status == TrialStatus.ONGOING.value
        assert plan_service.marketing_name == trial_plan.marketing_name
        assert plan_service.plan_name == trial_plan.value
        assert plan_service.billing_rate == trial_plan.billing_rate
        assert plan_service.base_unit_price == trial_plan.base_unit_price
        assert plan_service.benefits == trial_plan.benefits
        assert plan_service.monthly_uploads_limit == None  # Not 250 since it's trialing
        assert plan_service.trial_total_days == trial_plan.trial_days

    def test_plan_service_sets_default_plan_data_values_correctly(self):
        current_org = OwnerFactory(
            plan=PlanName.CODECOV_PRO_MONTHLY.value,
            stripe_subscription_id="test-sub-123",
            plan_user_count=20,
            plan_activated_users=[44],
            plan_auto_activate=False,
        )
        current_org.save()

        plan_service = PlanService(current_org=current_org)
        plan_service.set_default_plan_data()

        assert current_org.plan == PlanName.BASIC_PLAN_NAME.value
        assert current_org.plan_user_count == 1
        assert current_org.plan_activated_users == None
        assert current_org.stripe_subscription_id == None
