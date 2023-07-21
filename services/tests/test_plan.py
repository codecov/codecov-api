from datetime import datetime, timedelta

from django.test import TestCase
from freezegun import freeze_time

from billing.constants import BASIC_PLAN_NAME
from codecov.commands.exceptions import ValidationError
from codecov_auth.tests.factories import OwnerFactory
from services.plan import (
    FREE_PLAN_REPRESENTATIONS,
    PlanService,
    TrialDaysAmount,
    TrialStatus,
)


@freeze_time("2023-06-19")
class PlanServiceTests(TestCase):
    def test_plan_service_trial_status_not_started(self):
        current_org = OwnerFactory(plan=BASIC_PLAN_NAME)
        plan_service = PlanService(current_org=current_org)

        assert plan_service.trial_status == TrialStatus.NOT_STARTED

    def test_plan_service_trial_status_expired(self):
        trial_start_date = datetime.utcnow()
        trial_end_date_expired = trial_start_date - timedelta(days=1)
        current_org = OwnerFactory(
            plan=BASIC_PLAN_NAME,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date_expired,
        )
        plan_service = PlanService(current_org=current_org)

        assert plan_service.trial_status == TrialStatus.EXPIRED

    def test_plan_service_trial_status_ongoing(self):
        trial_start_date = datetime.utcnow()
        trial_end_date_ongoing = trial_start_date + timedelta(days=5)
        current_org = OwnerFactory(
            plan=BASIC_PLAN_NAME,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date_ongoing,
        )
        plan_service = PlanService(current_org=current_org)

        assert plan_service.trial_status == TrialStatus.ONGOING

    # TODO: uncomment this when trial_status logic is adjusted
    # def test_plan_service_trial_status_cannot_trial_if_current_paid_customer(self):
    #     current_org_with_paid_plan = OwnerFactory(
    #         plan=BASIC_PLAN_NAME,
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
            plan=BASIC_PLAN_NAME,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
            stripe_customer_id="test_id_123123",
        )
        plan_service = PlanService(current_org=current_org_with_paid_plan)
        assert plan_service.trial_status == TrialStatus.CANNOT_TRIAL

    def test_plan_service_start_trial_errors_if_status_is_not_started(self):
        trial_start_date = datetime.utcnow()
        trial_end_date = trial_start_date + timedelta(
            days=TrialDaysAmount.CODECOV_SENTRY.value
        )
        current_org = OwnerFactory(
            plan=BASIC_PLAN_NAME,
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
            plan=BASIC_PLAN_NAME,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
        )
        plan_service = PlanService(current_org=current_org)

        plan_service.start_trial()
        assert current_org.trial_start_date == datetime.utcnow()
        assert current_org.trial_end_date == datetime.utcnow() + timedelta(
            days=TrialDaysAmount.CODECOV_SENTRY.value
        )

    def test_plan_service_returns_plan_data_for_non_trial_basic_plan(self):
        trial_start_date = None
        trial_end_date = None
        current_org = OwnerFactory(
            plan=BASIC_PLAN_NAME,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
        )
        plan_service = PlanService(current_org=current_org)

        basic_plan = FREE_PLAN_REPRESENTATIONS[BASIC_PLAN_NAME]
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

    def test_plan_service_returns_plan_data_for_trialing_basic_plan(self):
        trial_start_date = datetime.utcnow()
        trial_end_date = datetime.utcnow() + timedelta(
            days=TrialDaysAmount.CODECOV_SENTRY.value
        )
        current_org = OwnerFactory(
            plan=BASIC_PLAN_NAME,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
        )
        plan_service = PlanService(current_org=current_org)

        basic_plan = FREE_PLAN_REPRESENTATIONS[BASIC_PLAN_NAME]
        assert plan_service.trial_status == TrialStatus.ONGOING
        assert plan_service.marketing_name == basic_plan.marketing_name
        assert plan_service.plan_name == basic_plan.value
        assert plan_service.billing_rate == basic_plan.billing_rate
        assert plan_service.base_unit_price == basic_plan.base_unit_price
        assert plan_service.benefits == basic_plan.benefits
        assert plan_service.monthly_uploads_limit == None  # Not 250 since it's trialing
        assert plan_service.trial_total_days == basic_plan.trial_days
