from datetime import timedelta

from django.forms import ValidationError
from django.test import TestCase
from django.utils import timezone
from freezegun import freeze_time

from billing.constants import BASIC_PLAN_NAME
from codecov_auth.tests.factories import OwnerFactory
from services.plan import TRIAL_DAYS_LENGTH, PlanService, TrialStatus


@freeze_time("2023-06-19")
class PlanServiceTests(TestCase):
    def test_plan_service_trial_status_not_started(self):
        current_org = OwnerFactory(plan=BASIC_PLAN_NAME)
        plan_service = PlanService(current_org=current_org)

        assert plan_service.trial_status == TrialStatus.NOT_STARTED

    def test_plan_service_trial_status_expired(self):
        trial_start_date = timezone.now().replace(tzinfo=None)
        trial_end_date_expired = trial_start_date - timedelta(days=1)
        current_org = OwnerFactory(
            plan=BASIC_PLAN_NAME,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date_expired,
        )
        plan_service = PlanService(current_org=current_org)

        assert plan_service.trial_status == TrialStatus.EXPIRED

    def test_plan_service_trial_status_ongoing(self):
        trial_start_date = timezone.now().replace(tzinfo=None)
        trial_end_date_ongoing = trial_start_date + timedelta(days=5)
        current_org = OwnerFactory(
            plan=BASIC_PLAN_NAME,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date_ongoing,
        )
        plan_service = PlanService(current_org=current_org)

        assert plan_service.trial_status == TrialStatus.ONGOING

    def test_plan_service_start_trial_errors_if_status_isnt_started(self):
        trial_start_date = timezone.now().replace(tzinfo=None)
        trial_end_date = trial_start_date + timedelta(days=TRIAL_DAYS_LENGTH)
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
        assert current_org.trial_start_date == timezone.now()
        assert current_org.trial_end_date == timezone.now() + timedelta(
            days=TRIAL_DAYS_LENGTH
        )

    def test_plan_service_expire_trial_preemptively_fails_if_no_trial_end_date(
        self,
    ):
        trial_end_date = None
        current_org = OwnerFactory(
            plan=BASIC_PLAN_NAME,
            trial_end_date=trial_end_date,
        )
        plan_service = PlanService(current_org=current_org)

        with self.assertRaises(ValidationError) as e:
            plan_service.expire_trial_preemptively()

    def test_plan_service_expire_trial_preemptively_succeeds_if_start_and_end_date(
        self,
    ):
        time_now = timezone.now().replace(tzinfo=None)
        time_in_three_days = time_now + timedelta(days=3)
        trial_start_date = time_now
        trial_end_date = time_now + timedelta(days=TRIAL_DAYS_LENGTH)
        current_org = OwnerFactory(
            plan=BASIC_PLAN_NAME,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
        )
        plan_service = PlanService(current_org=current_org)

        with freeze_time(time_in_three_days) as frozen_time:
            plan_service.expire_trial_preemptively()
            assert current_org.trial_start_date == time_now
            assert current_org.trial_end_date.replace(tzinfo=None) == time_in_three_days
