from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.test import TestCase
from freezegun import freeze_time

from codecov_auth.management.commands.set_trial_status_values import Command
from codecov_auth.models import Owner
from codecov_auth.tests.factories import OwnerFactory
from plan.constants import PlanNames, TrialStatus


@freeze_time("2023-07-17T00:00:00")
class OwnerCommandTestCase(TestCase):
    def setUp(self):
        self.command_instance = BaseCommand()
        now = datetime.utcnow()
        later = now + timedelta(days=3)
        yesterday = now + timedelta(days=-1)
        much_before = now + timedelta(days=-20)
        # NOT_STARTED
        self.not_started_owner = OwnerFactory(
            username="one",
            service="github",
            plan=PlanNames.BASIC_PLAN_NAME.value,
            trial_start_date=None,
            trial_end_date=None,
            trial_status=None,
            stripe_customer_id=None,
        )
        # ONGOING
        self.ongoing_owner = OwnerFactory(
            username="two",
            service="github",
            plan=PlanNames.SENTRY_MONTHLY.value,
            trial_start_date=now,
            trial_end_date=later,
            trial_status=None,
        )
        # EXPIRED
        self.expired_owner = OwnerFactory(
            username="three",
            service="github",
            plan=PlanNames.SENTRY_MONTHLY.value,
            trial_start_date=much_before,
            trial_end_date=yesterday,
            trial_status=None,
        )
        # # CANNOT_TRIAL
        self.unsupported_plan_owner = OwnerFactory(
            username="four", service="github", plan="v4-50m", trial_status=None
        )
        self.previously_paid_customer = OwnerFactory(
            username="five",
            service="github",
            plan=PlanNames.BASIC_PLAN_NAME.value,
            stripe_customer_id="test-cus-123",
            stripe_subscription_id="test-sub-456",
            trial_start_date=None,
            trial_end_date=None,
            trial_status=None,
        )

    def test_set_trial_status_values(self):
        Command.handle(self.command_instance, None, {})

        all_owners = Owner.objects.all()
        # assert all_owners.filter(username="one").first().trial_status == TrialStatus.NOT_STARTED.value
        assert (
            all_owners.filter(username="two").first().trial_status
            == TrialStatus.ONGOING.value
        )
        assert (
            all_owners.filter(username="three").first().trial_status
            == TrialStatus.EXPIRED.value
        )
        assert (
            all_owners.filter(username="four").first().trial_status
            == TrialStatus.CANNOT_TRIAL.value
        )
        assert (
            all_owners.filter(username="five").first().trial_status
            == TrialStatus.CANNOT_TRIAL.value
        )
