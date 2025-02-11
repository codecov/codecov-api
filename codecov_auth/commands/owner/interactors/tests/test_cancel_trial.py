from datetime import datetime, timedelta

import pytest
from asgiref.sync import async_to_sync
from django.test import TransactionTestCase
from freezegun import freeze_time
from shared.django_apps.codecov.commands.exceptions import ValidationError
from shared.django_apps.codecov_auth.tests.factories import PlanFactory, TierFactory
from shared.django_apps.core.tests.factories import OwnerFactory
from shared.plan.constants import DEFAULT_FREE_PLAN, PlanName, TierName, TrialStatus

from codecov.commands.exceptions import Unauthorized
from codecov.commands.exceptions import ValidationError as CodecovValidationError
from codecov_auth.models import Owner

from ..cancel_trial import CancelTrialInteractor


class CancelTrialInteractorTest(TransactionTestCase):
    def setUp(self):
        self.tier = TierFactory(tier_name=DEFAULT_FREE_PLAN)
        self.plan = PlanFactory(tier=self.tier)

    @async_to_sync
    def execute(self, current_user, org_username=None):
        current_user = current_user
        return CancelTrialInteractor(current_user, "github").execute(
            org_username=org_username,
        )

    def test_cancel_trial_raises_exception_when_owner_is_not_in_db(self):
        current_user = OwnerFactory(
            username="random-user-123",
            service="github",
            plan=self.plan.name,
        )
        with pytest.raises(CodecovValidationError):
            self.execute(current_user=current_user, org_username="some-other-username")

    def test_cancel_trial_raises_exception_when_current_user_not_part_of_org(self):
        current_user = OwnerFactory(
            username="random-user-123",
            service="github",
            plan=self.plan.name,
        )
        OwnerFactory(
            username="random-user-456",
            service="github",
            plan=self.plan.name,
        )
        with pytest.raises(Unauthorized):
            self.execute(current_user=current_user, org_username="random-user-456")

    @freeze_time("2022-01-01T00:00:00")
    def test_cancel_trial_raises_exception_when_owners_trial_status_is_not_started(
        self,
    ):
        trial_start_date = None
        trial_end_date = None
        current_user = OwnerFactory(
            username="random-user-123",
            service="github",
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
            plan=self.plan.name,
        )
        with pytest.raises(ValidationError):
            self.execute(current_user=current_user, org_username=current_user.username)

    @freeze_time("2022-01-01T00:00:00")
    def test_cancel_trial_raises_exception_when_owners_trial_status_is_expired(self):
        now = datetime.now()
        trial_start_date = now + timedelta(days=-10)
        trial_end_date = now + timedelta(days=-4)
        current_user = OwnerFactory(
            username="random-user-123",
            service="github",
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
            plan=self.plan.name,
        )
        with pytest.raises(ValidationError):
            self.execute(current_user=current_user, org_username=current_user.username)

    @freeze_time("2022-01-01T00:00:00")
    def test_cancel_trial_starts_trial_for_org_that_has_trial_ongoing(self):
        now = datetime.now()
        trial_start_date = now
        trial_end_date = now + timedelta(days=3)
        trial_tier = TierFactory(tier_name=TierName.TRIAL.value)
        trial_plan = PlanFactory(tier=trial_tier, name=PlanName.TRIAL_PLAN_NAME.value)
        current_user: Owner = OwnerFactory(
            username="random-user-123",
            service="github",
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
            trial_status=TrialStatus.ONGOING.value,
            plan=trial_plan.name,
        )
        self.execute(current_user=current_user, org_username=current_user.username)
        current_user.refresh_from_db()

        now = datetime.now()
        assert current_user.trial_end_date == now
        assert current_user.trial_status == TrialStatus.EXPIRED.value
        assert current_user.plan == DEFAULT_FREE_PLAN
        assert current_user.plan_activated_users is None
        assert current_user.plan_user_count == 1
        assert current_user.stripe_subscription_id is None
