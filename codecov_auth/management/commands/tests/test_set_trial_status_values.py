from datetime import UTC, datetime, timedelta

from django.core.management.base import BaseCommand
from django.test import TestCase
from freezegun import freeze_time

from codecov_auth.management.commands.set_trial_status_values import Command
from codecov_auth.models import Owner
from codecov_auth.tests.factories import OwnerFactory
from plan.constants import PlanName, TrialStatus


@freeze_time("2023-07-17T00:00:00")
class OwnerCommandTestCase(TestCase):
    def setUp(self):
        self.command_instance = BaseCommand()
        now = datetime.now()
        later = now + timedelta(days=3)
        yesterday = now + timedelta(days=-1)
        much_before = now + timedelta(days=-20)

        # NOT_STARTED
        self.not_started_basic_owner = OwnerFactory(
            username="one",
            service="github",
            plan=PlanName.BASIC_PLAN_NAME.value,
            stripe_customer_id=None,
            trial_status=None,
        )
        self.not_started_free_owner = OwnerFactory(
            username="two",
            service="github",
            plan=PlanName.FREE_PLAN_NAME.value,
            stripe_customer_id=None,
            trial_status=None,
        )

        # ONGOING
        self.sentry_plan_ongoing_owner = OwnerFactory(
            username="three",
            service="github",
            plan=PlanName.SENTRY_MONTHLY.value,
            trial_start_date=now,
            trial_end_date=later,
            trial_status=None,
        )

        # EXPIRED
        self.sentry_plan_expired_owner_with_trial_dates = OwnerFactory(
            username="four",
            service="github",
            plan=PlanName.SENTRY_MONTHLY.value,
            stripe_customer_id="test-cus-123",
            stripe_subscription_id="test-sub-123",
            trial_start_date=much_before,
            trial_end_date=yesterday,
            trial_status=None,
        )
        self.sentry_expired_owner_without_trial_dates = OwnerFactory(
            username="five",
            service="github",
            plan=PlanName.SENTRY_YEARLY.value,
            stripe_customer_id="test-cus-123",
            stripe_subscription_id="test-sub-123",
            trial_start_date=None,
            trial_end_date=None,
            trial_status=None,
        )
        self.expired_owner_with_basic_plan_with_trial_dates = OwnerFactory(
            username="six",
            service="github",
            plan=PlanName.BASIC_PLAN_NAME.value,
            trial_start_date=much_before,
            trial_end_date=yesterday,
            stripe_customer_id="test-cus-123",
            trial_status=None,
        )

        # CANNOT_TRIAL
        self.unsupported_trial_plan_owner = OwnerFactory(
            username="seven",
            service="github",
            plan=PlanName.ENTERPRISE_CLOUD_MONTHLY.value,
            trial_status=None,
        )
        self.currently_paid_owner_without_trial_dates = OwnerFactory(
            username="eight",
            service="github",
            plan=PlanName.CODECOV_PRO_MONTHLY.value,
            stripe_customer_id="test-cus-123",
            stripe_subscription_id="test-sub-123",
            trial_start_date=None,
            trial_end_date=None,
            trial_status=None,
        )
        self.previously_paid_owner_that_is_now_basic = OwnerFactory(
            username="nine",
            service="github",
            plan=PlanName.BASIC_PLAN_NAME.value,
            stripe_customer_id="test-cus-123",
            trial_start_date=None,
            trial_end_date=None,
            trial_status=None,
        )
        self.invoiced_customer_monthly_plan = OwnerFactory(
            username="ten",
            service="github",
            plan=PlanName.CODECOV_PRO_MONTHLY.value,
            stripe_customer_id=None,
            stripe_subscription_id=None,
        )
        self.invoiced_customer_yearly_plan = OwnerFactory(
            username="eleven",
            service="github",
            plan=PlanName.CODECOV_PRO_YEARLY.value,
            stripe_customer_id=None,
            stripe_subscription_id=None,
        )

    def test_set_trial_status_values(self):
        Command.handle(self.command_instance, trial_status_type="all")

        all_owners = Owner.objects.all()

        assert (
            all_owners.filter(username="one").first().trial_status
            == TrialStatus.NOT_STARTED.value
        )
        assert (
            all_owners.filter(username="two").first().trial_status
            == TrialStatus.NOT_STARTED.value
        )
        assert (
            all_owners.filter(username="three").first().trial_status
            == TrialStatus.ONGOING.value
        )
        assert (
            all_owners.filter(username="four").first().trial_status
            == TrialStatus.EXPIRED.value
        )
        assert (
            all_owners.filter(username="five").first().trial_status
            == TrialStatus.EXPIRED.value
        )
        assert (
            all_owners.filter(username="six").first().trial_status
            == TrialStatus.EXPIRED.value
        )
        assert (
            all_owners.filter(username="seven").first().trial_status
            == TrialStatus.CANNOT_TRIAL.value
        )
        assert (
            all_owners.filter(username="eight").first().trial_status
            == TrialStatus.CANNOT_TRIAL.value
        )
        assert (
            all_owners.filter(username="nine").first().trial_status
            == TrialStatus.CANNOT_TRIAL.value
        )
        assert (
            all_owners.filter(username="ten").first().trial_status
            == TrialStatus.CANNOT_TRIAL.value
        )
        assert (
            all_owners.filter(username="eleven").first().trial_status
            == TrialStatus.CANNOT_TRIAL.value
        )
