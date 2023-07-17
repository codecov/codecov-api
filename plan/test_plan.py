from datetime import datetime, timedelta

from django.forms import ValidationError
from django.test import TestCase
from freezegun import freeze_time

from codecov_auth.tests.factories import OwnerFactory
from plan.constants import (
    FREE_PLAN_REPRESENTATIONS,
    TRIAL_PLAN_REPRESENTATION,
    PlanNames,
    TrialDaysAmount,
    TrialStatus,
)
from plan.service import PlanService


@freeze_time("2023-06-19")
class PlanServiceTests(TestCase):
    def test_plan_service_trial_status_not_started(self):
        current_org = OwnerFactory(plan=PlanNames.BASIC_PLAN_NAME.value)
        plan_service = PlanService(current_org=current_org)

        assert plan_service.trial_status == TrialStatus.NOT_STARTED

    def test_plan_service_trial_status_expired(self):
        trial_start_date = datetime.utcnow()
        trial_end_date_expired = trial_start_date - timedelta(days=1)
        current_org = OwnerFactory(
            plan=PlanNames.BASIC_PLAN_NAME.value,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date_expired,
        )
        plan_service = PlanService(current_org=current_org)

        assert plan_service.trial_status == TrialStatus.EXPIRED

    def test_plan_service_trial_status_ongoing(self):
        trial_start_date = datetime.utcnow()
        trial_end_date_ongoing = trial_start_date + timedelta(days=5)
        current_org = OwnerFactory(
            plan=PlanNames.BASIC_PLAN_NAME.value,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date_ongoing,
        )
        plan_service = PlanService(current_org=current_org)

        assert plan_service.trial_status == TrialStatus.ONGOING

    # TODO: uncomment this when trial_status logic is adjusted
    # def test_plan_service_trial_status_cannot_trial_if_current_paid_customer(self):
    #     current_org_with_paid_plan = OwnerFactory(
    #         plan=PlanNames.BASIC_PLAN_NAME.value,
    #         trial_start_date=None,
    #         trial_end_date=None,
    #         stripe_customer_id="test_id_123123",
    #     )
    #     plan_service = PlanService(current_org=current_org_with_paid_plan)
    #     assert plan_service.trial_status == TrialStatus.CANNOT_TRIAL

    def test_plan_service_trial_status_never_started_if_it_used_to_be_paid_customer(
        self,
    ):
        now = datetime.utcnow()
        trial_start_date = now
        trial_end_date = now
        current_org_with_paid_plan = OwnerFactory(
            plan=PlanNames.BASIC_PLAN_NAME.value,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
            stripe_customer_id="test_id_123123",
        )
        plan_service = PlanService(current_org=current_org_with_paid_plan)
        assert plan_service.trial_status == TrialStatus.CANNOT_TRIAL

    def test_plan_service_start_trial_errors_if_status_isnt_started(self):
        trial_start_date = datetime.utcnow()
        trial_end_date = trial_start_date + timedelta(
            days=TrialDaysAmount.CODECOV_SENTRY.value
        )
        current_org = OwnerFactory(
            plan=PlanNames.BASIC_PLAN_NAME.value,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
        )
        plan_service = PlanService(current_org=current_org)

        with self.assertRaises(ValidationError) as e:
            plan_service.start_trial()

    def test_plan_service_start_trial_succeeds_if_no_start_or_end_date(self):
        trial_start_date = None
        trial_end_date = None
        current_org = OwnerFactory(
            plan=PlanNames.BASIC_PLAN_NAME.value,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
        )
        plan_service = PlanService(current_org=current_org)

        plan_service.start_trial()
        assert current_org.trial_start_date == datetime.utcnow()
        assert current_org.trial_end_date == datetime.utcnow() + timedelta(
            days=TrialDaysAmount.CODECOV_SENTRY.value
        )

    def test_plan_service_expire_trial_for_ongoing_trial(
        self,
    ):
        time_now = datetime.utcnow()
        trial_start_date = time_now
        trial_end_date = time_now + timedelta(days=TrialDaysAmount.CODECOV_SENTRY.value)
        current_org = OwnerFactory(
            plan=PlanNames.BASIC_PLAN_NAME.value,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
        )
        plan_service = PlanService(current_org=current_org)
        plan_service.expire_trial()

        current_org.refresh_from_db()

        assert plan_service.trial_end_date == time_now
        # TODO: Uncomment when trial_status is derived from DB column
        # assert plan_service.trial_status == TrialStatus.EXPIRED

    def test_plan_service_expire_trial_preemptively_fails_if_no_trial_end_date(
        self,
    ):
        trial_end_date = None
        current_org = OwnerFactory(
            plan=PlanNames.BASIC_PLAN_NAME.value,
            trial_end_date=trial_end_date,
        )
        plan_service = PlanService(current_org=current_org)

        with self.assertRaises(ValidationError) as e:
            plan_service.expire_trial_preemptively()

    def test_plan_service_expire_trial_preemptively_succeeds_if_start_and_end_date(
        self,
    ):
        time_now = datetime.utcnow()
        time_in_three_days = time_now + timedelta(days=3)
        trial_start_date = time_now
        trial_end_date = time_now + timedelta(days=TrialDaysAmount.CODECOV_SENTRY.value)
        current_org = OwnerFactory(
            plan=PlanNames.BASIC_PLAN_NAME.value,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
        )
        plan_service = PlanService(current_org=current_org)

        with freeze_time(time_in_three_days) as frozen_time:
            plan_service.expire_trial_preemptively()
            assert current_org.trial_start_date == time_now
            assert current_org.trial_end_date == time_in_three_days

    def test_plan_service_returns_plan_data_for_basic_plan_non_trial(self):
        trial_start_date = None
        trial_end_date = None
        current_org = OwnerFactory(
            plan=PlanNames.BASIC_PLAN_NAME.value,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
        )
        plan_service = PlanService(current_org=current_org)

        basic_plan = FREE_PLAN_REPRESENTATIONS[PlanNames.BASIC_PLAN_NAME.value]
        assert plan_service.trial_status == TrialStatus.NOT_STARTED
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
            plan=PlanNames.TRIAL_PLAN_NAME.value,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
        )
        plan_service = PlanService(current_org=current_org)

        trial_plan = TRIAL_PLAN_REPRESENTATION[PlanNames.TRIAL_PLAN_NAME.value]
        assert plan_service.trial_status == TrialStatus.ONGOING
        assert plan_service.marketing_name == trial_plan.marketing_name
        assert plan_service.plan_name == trial_plan.value
        assert plan_service.billing_rate == trial_plan.billing_rate
        assert plan_service.base_unit_price == trial_plan.base_unit_price
        assert plan_service.benefits == trial_plan.benefits
        assert plan_service.monthly_uploads_limit == None  # Not 250 since it's trialing
        assert plan_service.trial_total_days == trial_plan.trial_days

    def test_plan_service_sets_default_plan_data_values_correctly(self):
        current_org = OwnerFactory(
            plan=PlanNames.CODECOV_PRO_MONTHLY.value,
            stripe_subscription_id="4kw23l4k",
            plan_user_count=20,
            plan_activated_users=[44],
            plan_auto_activate=False,
        )
        current_org.save()

        plan_service = PlanService(current_org=current_org)
        plan_service.set_default_plan_data()

        assert current_org.plan == PlanNames.BASIC_PLAN_NAME.value
        assert current_org.plan_user_count == 1
        assert current_org.plan_activated_users == None
        assert current_org.stripe_subscription_id == None
