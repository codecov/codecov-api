import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TestCase
from freezegun import freeze_time
from pytest import raises
from shared.django_apps.codecov_auth.tests.factories import AccountsUsersFactory

from codecov.commands.exceptions import ValidationError
from codecov_auth.tests.factories import AccountFactory, OwnerFactory
from plan.constants import (
    BASIC_PLAN,
    FREE_PLAN,
    FREE_PLAN_REPRESENTATIONS,
    PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS,
    SENTRY_PAID_USER_PLAN_REPRESENTATIONS,
    TEAM_PLAN_REPRESENTATIONS,
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
        trial_start_date = datetime.now()
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
        trial_start_date = datetime.now()
        trial_end_date_ongoing = trial_start_date + timedelta(days=5)
        current_org = OwnerFactory(
            plan=PlanName.TRIAL_PLAN_NAME.value,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date_ongoing,
            trial_status=TrialStatus.ONGOING.value,
        )
        plan_service = PlanService(current_org=current_org)

        assert plan_service.trial_status == TrialStatus.ONGOING.value
        assert plan_service.is_org_trialing == True

    def test_plan_service_expire_trial_when_upgrading_successful_if_trial_is_not_started(
        self,
    ):
        current_org_with_ongoing_trial = OwnerFactory(
            plan=PlanName.BASIC_PLAN_NAME.value,
            trial_start_date=None,
            trial_end_date=None,
            trial_status=TrialStatus.NOT_STARTED.value,
        )
        plan_service = PlanService(current_org=current_org_with_ongoing_trial)
        plan_service.expire_trial_when_upgrading()
        assert current_org_with_ongoing_trial.trial_status == TrialStatus.EXPIRED.value
        assert current_org_with_ongoing_trial.plan_activated_users is None
        assert current_org_with_ongoing_trial.plan_user_count == 1
        assert current_org_with_ongoing_trial.trial_end_date == datetime.now()

    def test_plan_service_expire_trial_when_upgrading_successful_if_trial_is_ongoing(
        self,
    ):
        trial_start_date = datetime.now()
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
        assert current_org_with_ongoing_trial.plan_activated_users is None
        assert current_org_with_ongoing_trial.plan_user_count == 1
        assert current_org_with_ongoing_trial.trial_end_date == datetime.now()

    def test_plan_service_expire_trial_users_pretrial_users_count_if_existing(
        self,
    ):
        trial_start_date = datetime.now()
        trial_end_date_ongoing = trial_start_date + timedelta(days=5)
        pretrial_users_count = 5
        current_org_with_ongoing_trial = OwnerFactory(
            plan=PlanName.BASIC_PLAN_NAME.value,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date_ongoing,
            trial_status=TrialStatus.ONGOING.value,
            pretrial_users_count=pretrial_users_count,
        )
        plan_service = PlanService(current_org=current_org_with_ongoing_trial)
        plan_service.expire_trial_when_upgrading()
        assert current_org_with_ongoing_trial.trial_status == TrialStatus.EXPIRED.value
        assert current_org_with_ongoing_trial.plan_activated_users is None
        assert current_org_with_ongoing_trial.plan_user_count == pretrial_users_count
        assert current_org_with_ongoing_trial.trial_end_date == datetime.now()

    def test_plan_service_start_trial_errors_if_status_is_ongoing(self):
        trial_start_date = datetime.now()
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
        current_owner = OwnerFactory()

        with self.assertRaises(ValidationError):
            plan_service.start_trial(current_owner=current_owner)

    def test_plan_service_start_trial_errors_if_status_is_expired(self):
        trial_start_date = datetime.now()
        trial_end_date = trial_start_date + timedelta(days=-1)
        current_org = OwnerFactory(
            plan=PlanName.BASIC_PLAN_NAME.value,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
            trial_status=TrialStatus.EXPIRED.value,
        )
        plan_service = PlanService(current_org=current_org)
        current_owner = OwnerFactory()

        with self.assertRaises(ValidationError):
            plan_service.start_trial(current_owner=current_owner)

    def test_plan_service_start_trial_errors_if_status_is_cannot_trial(self):
        current_org = OwnerFactory(
            plan=PlanName.BASIC_PLAN_NAME.value,
            trial_start_date=None,
            trial_end_date=None,
            trial_status=TrialStatus.CANNOT_TRIAL.value,
        )
        plan_service = PlanService(current_org=current_org)
        current_owner = OwnerFactory()

        with self.assertRaises(ValidationError):
            plan_service.start_trial(current_owner=current_owner)

    def test_plan_service_start_trial_errors_owners_plan_is_not_a_free_plan(self):
        current_org = OwnerFactory(
            plan=PlanName.CODECOV_PRO_MONTHLY.value,
            trial_start_date=None,
            trial_end_date=None,
            trial_status=TrialStatus.CANNOT_TRIAL.value,
        )
        plan_service = PlanService(current_org=current_org)
        current_owner = OwnerFactory()

        with self.assertRaises(ValidationError):
            plan_service.start_trial(current_owner=current_owner)

    def test_plan_service_start_trial_succeeds_if_trial_has_not_started(self):
        trial_start_date = None
        trial_end_date = None
        plan_user_count = 5
        current_org = OwnerFactory(
            plan=PlanName.BASIC_PLAN_NAME.value,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
            trial_status=TrialStatus.NOT_STARTED.value,
            plan_user_count=plan_user_count,
        )
        plan_service = PlanService(current_org=current_org)
        current_owner = OwnerFactory()

        plan_service.start_trial(current_owner=current_owner)
        assert current_org.trial_start_date == datetime.now()
        assert current_org.trial_end_date == datetime.now() + timedelta(
            days=TrialDaysAmount.CODECOV_SENTRY.value
        )
        assert current_org.trial_status == TrialStatus.ONGOING.value
        assert current_org.plan == PlanName.TRIAL_PLAN_NAME.value
        assert current_org.pretrial_users_count == plan_user_count
        assert current_org.plan_user_count == TRIAL_PLAN_SEATS
        assert current_org.plan_auto_activate == True
        assert current_org.trial_fired_by == current_owner.ownerid

    def test_plan_service_start_trial_manually(self):
        trial_start_date = None
        trial_end_date = None
        plan_user_count = 5
        current_org = OwnerFactory(
            plan=PlanName.BASIC_PLAN_NAME.value,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
            trial_status=TrialStatus.NOT_STARTED.value,
            plan_user_count=plan_user_count,
        )
        plan_service = PlanService(current_org=current_org)
        current_owner = OwnerFactory()

        plan_service.start_trial_manually(
            current_owner=current_owner, end_date="2024-01-01 00:00:00"
        )
        assert current_org.trial_start_date == datetime.now()
        assert current_org.trial_end_date == "2024-01-01 00:00:00"
        assert current_org.trial_status == TrialStatus.ONGOING.value
        assert current_org.plan == PlanName.TRIAL_PLAN_NAME.value
        assert current_org.pretrial_users_count == plan_user_count
        assert current_org.plan_user_count == TRIAL_PLAN_SEATS
        assert current_org.plan_auto_activate == True
        assert current_org.trial_fired_by == current_owner.ownerid

    def test_plan_service_start_trial_manually_already_on_paid_plan(self):
        current_org = OwnerFactory(
            plan=PlanName.CODECOV_PRO_MONTHLY.value,
            trial_start_date=None,
            trial_end_date=None,
            trial_status=TrialStatus.NOT_STARTED.value,
        )
        plan_service = PlanService(current_org=current_org)
        current_owner = OwnerFactory()

        with self.assertRaises(ValidationError):
            plan_service.start_trial_manually(
                current_owner=current_owner, end_date="2024-01-01 00:00:00"
            )

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
        assert plan_service.current_org == current_org
        assert plan_service.trial_status == TrialStatus.NOT_STARTED.value
        assert plan_service.marketing_name == basic_plan.marketing_name
        assert plan_service.plan_name == basic_plan.value
        assert plan_service.tier_name == basic_plan.tier_name
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
        trial_start_date = datetime.now()
        trial_end_date = datetime.now() + timedelta(
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
        assert plan_service.tier_name == trial_plan.tier_name
        assert plan_service.billing_rate == trial_plan.billing_rate
        assert plan_service.base_unit_price == trial_plan.base_unit_price
        assert plan_service.benefits == trial_plan.benefits
        assert plan_service.monthly_uploads_limit is None  # Not 250 since it's trialing
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
        assert current_org.plan_activated_users is None
        assert current_org.stripe_subscription_id is None

    def test_plan_service_returns_if_owner_has_trial_dates(self):
        current_org = OwnerFactory(
            plan=PlanName.CODECOV_PRO_MONTHLY.value,
            trial_start_date=datetime.now(),
            trial_end_date=datetime.now() + timedelta(days=14),
        )
        current_org.save()

        plan_service = PlanService(current_org=current_org)

        assert plan_service.has_trial_dates == True

    def test_plan_service_has_seats_left(self):
        current_org = OwnerFactory(
            plan=PlanName.TRIAL_PLAN_NAME.value,
            plan_user_count=6,
            plan_activated_users=[i for i in range(5)],
        )
        plan_service = PlanService(current_org=current_org)

        assert asyncio.run(plan_service.has_seats_left) == True

    def test_plan_service_has_no_seats_left(self):
        current_org = OwnerFactory(
            plan=PlanName.TRIAL_PLAN_NAME.value,
            plan_user_count=5,
            plan_activated_users=[i for i in range(5)],
        )
        plan_service = PlanService(current_org=current_org)

        assert asyncio.run(plan_service.has_seats_left) == False

    def test_plan_service_update_plan_invalid_name(self):
        current_org = OwnerFactory(plan=PlanName.BASIC_PLAN_NAME.value)
        plan_service = PlanService(current_org=current_org)

        with raises(ValueError, match="Unsupported plan"):
            plan_service.update_plan(name="blah", user_count=1)

    def test_plan_service_update_plan_invalid_user_count(self):
        current_org = OwnerFactory(plan=PlanName.BASIC_PLAN_NAME.value)
        plan_service = PlanService(current_org=current_org)

        with raises(ValueError, match="Quantity Needed"):
            plan_service.update_plan(
                name=PlanName.BASIC_PLAN_NAME.value, user_count=None
            )

    def test_plan_service_update_plan_succeeds(self):
        current_org = OwnerFactory(plan=PlanName.BASIC_PLAN_NAME.value)
        plan_service = PlanService(current_org=current_org)

        plan_service.update_plan(name=PlanName.TEAM_MONTHLY.value, user_count=8)

        assert current_org.plan == PlanName.TEAM_MONTHLY.value
        assert current_org.plan_user_count == 8

    def test_has_account(self):
        current_org = OwnerFactory()
        plan_service = PlanService(current_org=current_org)
        self.assertFalse(plan_service.has_account)

        current_org.account = AccountFactory()
        current_org.save()
        plan_service = PlanService(current_org=current_org)
        self.assertTrue(plan_service.has_account)

    def test_plan_data_has_account(self):
        current_org = OwnerFactory(plan=PlanName.BASIC_PLAN_NAME.value)
        plan_service = PlanService(current_org=current_org)
        self.assertEqual(plan_service.plan_name, PlanName.BASIC_PLAN_NAME.value)

        current_org.account = AccountFactory(plan=PlanName.CODECOV_PRO_YEARLY.value)
        current_org.save()
        plan_service = PlanService(current_org=current_org)
        self.assertEqual(plan_service.plan_name, PlanName.CODECOV_PRO_YEARLY.value)

    def test_plan_user_count_has_account(self):
        org = OwnerFactory(plan=PlanName.BASIC_PLAN_NAME.value, plan_user_count=5)
        account = AccountFactory(
            plan=PlanName.BASIC_PLAN_NAME.value, plan_seat_count=50, free_seat_count=3
        )

        plan_service = PlanService(current_org=org)
        self.assertEqual(plan_service.plan_user_count, 5)

        org.account = account
        org.save()
        plan_service = PlanService(current_org=org)
        self.assertEqual(plan_service.plan_user_count, 53)

    def test_has_seats_left_has_account(self):
        org = OwnerFactory(
            plan=PlanName.BASIC_PLAN_NAME.value,
            plan_user_count=5,
            plan_activated_users=[1, 2, 3],
        )
        account = AccountFactory(
            plan=PlanName.BASIC_PLAN_NAME.value, plan_seat_count=5, free_seat_count=3
        )
        for i in range(8):
            AccountsUsersFactory(account=account)

        plan_service = PlanService(current_org=org)
        self.assertTrue(asyncio.run(plan_service.has_seats_left))

        org.account = account
        org.save()
        plan_service = PlanService(current_org=org)
        self.assertFalse(asyncio.run(plan_service.has_seats_left))


class AvailablePlansBeforeTrial(TestCase):
    """
    - users-basic, no trial -> users-pr-inappm/y, users-basic
    - users-free, no trial -> users-pr-inappm/y, users-basic, users-free
    - users-teamm/y, no trial -> users-pr-inappm/y, users-basic, users-teamm/y
    - users-pr-inappm/y, no trial -> users-pr-inappm/y, users-basic
    - sentry customer, users-basic, no trial -> users-pr-inappm/y, users-sentrym/y, users-basic
    - sentry customer, users-teamm/y, no trial -> users-pr-inappm/y, users-sentrym/y, users-basic, users-teamm/y
    - sentry customer, users-sentrym/y, no trial -> users-pr-inappm/y, users-sentrym/y, users-basic
    """

    def setUp(self):
        self.current_org = OwnerFactory(
            trial_start_date=None,
            trial_end_date=None,
            trial_status=TrialStatus.NOT_STARTED.value,
        )
        self.owner = OwnerFactory()

    def test_available_plans_for_basic_plan_non_trial(
        self,
    ):
        self.current_org.plan = PlanName.BASIC_PLAN_NAME.value
        self.current_org.save()

        plan_service = PlanService(current_org=self.current_org)

        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += TEAM_PLAN_REPRESENTATIONS.values()

        assert plan_service.available_plans(owner=self.owner) == expected_result

    def test_available_plans_for_free_plan_non_trial(
        self,
    ):
        self.current_org.plan = PlanName.FREE_PLAN_NAME.value
        self.current_org.save()

        plan_service = PlanService(current_org=self.current_org)

        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result.append(FREE_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += TEAM_PLAN_REPRESENTATIONS.values()

        assert plan_service.available_plans(owner=self.owner) == expected_result

    def test_available_plans_for_team_plan_non_trial(
        self,
    ):
        self.current_org.plan = PlanName.TEAM_MONTHLY.value
        self.current_org.save()

        plan_service = PlanService(current_org=self.current_org)

        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += TEAM_PLAN_REPRESENTATIONS.values()

        assert plan_service.available_plans(owner=self.owner) == expected_result

    def test_available_plans_for_pro_plan_non_trial(self):
        self.current_org.plan = PlanName.CODECOV_PRO_MONTHLY.value
        self.current_org.save()

        plan_service = PlanService(current_org=self.current_org)

        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += TEAM_PLAN_REPRESENTATIONS.values()

        assert plan_service.available_plans(owner=self.owner) == expected_result

    @patch("services.sentry.is_sentry_user")
    def test_available_plans_for_sentry_customer_basic_plan_non_trial(
        self, is_sentry_user
    ):
        is_sentry_user.return_value = True
        self.current_org.plan = PlanName.BASIC_PLAN_NAME.value
        self.current_org.save()

        plan_service = PlanService(current_org=self.current_org)

        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += SENTRY_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += TEAM_PLAN_REPRESENTATIONS.values()

        assert plan_service.available_plans(owner=self.owner) == expected_result

    @patch("services.sentry.is_sentry_user")
    def test_available_plans_for_sentry_customer_team_plan_non_trial(
        self, is_sentry_user
    ):
        is_sentry_user.return_value = True
        self.current_org.plan = PlanName.TEAM_MONTHLY.value
        self.current_org.save()

        plan_service = PlanService(current_org=self.current_org)

        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += SENTRY_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += TEAM_PLAN_REPRESENTATIONS.values()

        assert plan_service.available_plans(owner=self.owner) == expected_result

    @patch("services.sentry.is_sentry_user")
    def test_available_plans_for_sentry_plan_non_trial(self, is_sentry_user):
        is_sentry_user.return_value = True
        self.current_org.plan = PlanName.SENTRY_MONTHLY.value
        self.current_org.save()

        plan_service = PlanService(current_org=self.current_org)

        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += SENTRY_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += TEAM_PLAN_REPRESENTATIONS.values()

        assert plan_service.available_plans(owner=self.owner) == expected_result


@freeze_time("2023-06-19")
class AvailablePlansExpiredTrialLessThanTenUsers(TestCase):
    """
    - users-basic, has trialed, less than 10 users -> users-pr-inappm/y, users-basic, users-teamm/y
    - users-teamm/y, has trialed, less than 10 users -> users-pr-inappm/y, users-basic, users-teamm/y
    - users-pr-inappm/y, has trialed, less than 10 users -> users-pr-inappm/y, users-basic, users-teamm/y
    - sentry customer, users-basic, has trialed, less than 10 users -> users-pr-inappm/y, users-sentrym/y, users-basic, users-teamm/y
    - sentry customer, users-teamm/y, has trialed, less than 10 users -> users-pr-inappm/y, users-sentrym/y, users-basic, users-teamm/y
    - sentry customer, users-sentrym/y, has trialed, less than 10 users -> users-pr-inappm/y, users-sentrym/y, users-basic, users-teamm/y
    """

    def setUp(self):
        self.current_org = OwnerFactory(
            trial_start_date=datetime.now() + timedelta(days=-10),
            trial_end_date=datetime.now() + timedelta(days=-3),
            trial_status=TrialStatus.EXPIRED.value,
            plan_user_count=3,
        )
        self.owner = OwnerFactory()

    def test_available_plans_for_basic_plan_expired_trial_less_than_10_users(
        self,
    ):
        self.current_org.plan = PlanName.BASIC_PLAN_NAME.value
        self.current_org.save()

        plan_service = PlanService(current_org=self.current_org)

        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += TEAM_PLAN_REPRESENTATIONS.values()

        assert plan_service.available_plans(owner=self.owner) == expected_result

    def test_available_plans_for_team_plan_expired_trial_less_than_10_users(
        self,
    ):
        self.current_org.plan = PlanName.TEAM_MONTHLY.value
        self.current_org.save()

        plan_service = PlanService(current_org=self.current_org)

        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += TEAM_PLAN_REPRESENTATIONS.values()

        assert plan_service.available_plans(owner=self.owner) == expected_result

    def test_available_plans_for_pro_plan_expired_trial_less_than_10_users(self):
        self.current_org.plan = PlanName.CODECOV_PRO_MONTHLY.value
        self.current_org.save()

        plan_service = PlanService(current_org=self.current_org)

        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += TEAM_PLAN_REPRESENTATIONS.values()

        assert plan_service.available_plans(owner=self.owner) == expected_result

    @patch("services.sentry.is_sentry_user")
    def test_available_plans_for_sentry_customer_basic_plan_expired_trial_less_than_10_users(
        self, is_sentry_user
    ):
        is_sentry_user.return_value = True
        self.current_org.plan = PlanName.BASIC_PLAN_NAME.value
        self.current_org.save()

        plan_service = PlanService(current_org=self.current_org)

        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += SENTRY_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += TEAM_PLAN_REPRESENTATIONS.values()

        assert plan_service.available_plans(owner=self.owner) == expected_result

    @patch("services.sentry.is_sentry_user")
    def test_available_plans_for_sentry_customer_team_plan_expired_trial_less_than_10_users(
        self, is_sentry_user
    ):
        is_sentry_user.return_value = True
        self.current_org.plan = PlanName.TEAM_MONTHLY.value
        self.current_org.save()

        plan_service = PlanService(current_org=self.current_org)

        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += SENTRY_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += TEAM_PLAN_REPRESENTATIONS.values()

        assert plan_service.available_plans(owner=self.owner) == expected_result

    @patch("services.sentry.is_sentry_user")
    def test_available_plans_for_sentry_plan_expired_trial_less_than_10_users(
        self, is_sentry_user
    ):
        is_sentry_user.return_value = True
        self.current_org.plan = PlanName.SENTRY_MONTHLY.value
        self.current_org.save()

        plan_service = PlanService(current_org=self.current_org)

        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += SENTRY_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += TEAM_PLAN_REPRESENTATIONS.values()

        assert plan_service.available_plans(owner=self.owner) == expected_result


@freeze_time("2023-06-19")
class AvailablePlansExpiredTrialMoreThanTenActivatedUsers(TestCase):
    """
    - users-pr-inappm/y, has trialed, more than 10 activated users -> users-pr-inappm/y, users-basic
    - sentry customer, users-basic, has trialed, more than 10 activated users -> users-pr-inappm/y, users-sentrym/y, users-basic
    - sentry customer, users-sentrym/y, has trialed, more than 10 activated users -> users-pr-inappm/y, users-sentrym/y, users-basic
    """

    def setUp(self):
        self.current_org = OwnerFactory(
            trial_start_date=datetime.now() + timedelta(days=-10),
            trial_end_date=datetime.now() + timedelta(days=-3),
            trial_status=TrialStatus.EXPIRED.value,
            plan_user_count=1,
            plan_activated_users=[i for i in range(13)],
        )
        self.owner = OwnerFactory()

    def test_available_plans_for_pro_plan_expired_trial_more_than_10_users(self):
        self.current_org.plan = PlanName.CODECOV_PRO_MONTHLY.value
        self.current_org.save()

        plan_service = PlanService(current_org=self.current_org)

        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()

        assert plan_service.available_plans(owner=self.owner) == expected_result

    @patch("services.sentry.is_sentry_user")
    def test_available_plans_for_sentry_customer_basic_plan_expired_trial_more_than_10_users(
        self, is_sentry_user
    ):
        is_sentry_user.return_value = True
        self.current_org.plan = PlanName.BASIC_PLAN_NAME.value
        self.current_org.save()

        plan_service = PlanService(current_org=self.current_org)

        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += SENTRY_PAID_USER_PLAN_REPRESENTATIONS.values()

        assert plan_service.available_plans(owner=self.owner) == expected_result

    @patch("services.sentry.is_sentry_user")
    def test_available_plans_for_sentry_plan_expired_trial_more_than_10_users(
        self, is_sentry_user
    ):
        is_sentry_user.return_value = True
        self.current_org.plan = PlanName.SENTRY_MONTHLY.value
        self.current_org.save()

        plan_service = PlanService(current_org=self.current_org)

        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += SENTRY_PAID_USER_PLAN_REPRESENTATIONS.values()

        assert plan_service.available_plans(owner=self.owner) == expected_result


@freeze_time("2023-06-19")
class AvailablePlansExpiredTrialMoreThanTenSeatsLessThanTenActivatedUsers(TestCase):
    """
    Tests that what matters for Team plan is activated users not the total seat count
    """

    def setUp(self):
        self.expected_result = []
        self.expected_result.append(BASIC_PLAN)
        self.expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        self.expected_result += TEAM_PLAN_REPRESENTATIONS.values()

    def test_currently_team_plan(self):
        self.current_org = OwnerFactory(
            plan_user_count=100,
            plan_activated_users=[i for i in range(10)],
            plan=PlanName.TEAM_MONTHLY.value,
        )
        self.owner = OwnerFactory()
        self.plan_service = PlanService(current_org=self.current_org)

        assert (
            self.plan_service.available_plans(owner=self.owner) == self.expected_result
        )

    def test_trial_expired(self):
        self.current_org = OwnerFactory(
            plan_user_count=100,
            plan_activated_users=[i for i in range(10)],
            trial_status=TrialStatus.EXPIRED.value,
            trial_start_date=datetime.now() + timedelta(days=-10),
            trial_end_date=datetime.now() + timedelta(days=-3),
        )
        self.owner = OwnerFactory()
        self.plan_service = PlanService(current_org=self.current_org)

        assert (
            self.plan_service.available_plans(owner=self.owner) == self.expected_result
        )

    def test_trial_ongoing(self):
        self.current_org = OwnerFactory(
            plan_user_count=100,
            plan_activated_users=[i for i in range(10)],
            trial_status=TrialStatus.ONGOING.value,
            trial_start_date=datetime.now() + timedelta(days=-10),
            trial_end_date=datetime.now() + timedelta(days=3),
        )
        self.owner = OwnerFactory()
        self.plan_service = PlanService(current_org=self.current_org)

        assert (
            self.plan_service.available_plans(owner=self.owner) == self.expected_result
        )

    def test_trial_not_started(self):
        self.current_org = OwnerFactory(
            plan_user_count=100,
            plan_activated_users=[i for i in range(10)],
            trial_status=TrialStatus.NOT_STARTED.value,
        )
        self.owner = OwnerFactory()
        self.plan_service = PlanService(current_org=self.current_org)

        self.expected_result = []
        self.expected_result.append(BASIC_PLAN)
        self.expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        self.expected_result += TEAM_PLAN_REPRESENTATIONS.values()
        assert (
            self.plan_service.available_plans(owner=self.owner) == self.expected_result
        )


@freeze_time("2023-06-19")
class AvailablePlansOngoingTrial(TestCase):
    """
    Non Sentry User is trialing
        when <=10 activated seats -> users-pr-inappm/y, users-basic, users-teamm/y
        when > 10 activated seats -> users-pr-inappm/y, users-basic
    Sentry User is trialing
        when <=10 activated seats -> users-pr-inappm/y, users-sentrym/y, users-basic, users-teamm/y
        when > 10 activated seats -> users-pr-inappm/y, users-sentrym/y, users-basic
    """

    def setUp(self):
        self.current_org = OwnerFactory(
            plan=PlanName.TRIAL_PLAN_NAME.value,
            trial_start_date=datetime.now(),
            trial_end_date=datetime.now() + timedelta(days=14),
            trial_status=TrialStatus.ONGOING.value,
            plan_user_count=1000,
            plan_activated_users=None,
        )
        self.owner = OwnerFactory()
        self.plan_service = PlanService(current_org=self.current_org)

    def test_non_sentry_user(self):
        # [Basic, Pro Monthly, Pro Yearly, Team Monthly, Team Yearly]
        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += TEAM_PLAN_REPRESENTATIONS.values()

        # Can do Team plan when plan_activated_users is null
        assert self.plan_service.available_plans(owner=self.owner) == expected_result

        self.current_org.plan_activated_users = [i for i in range(10)]
        self.current_org.save()

        # Can do Team plan when at 10 activated users
        assert self.plan_service.available_plans(owner=self.owner) == expected_result

        self.current_org.plan_activated_users = [i for i in range(11)]
        self.current_org.save()

        # [Basic, Pro Monthly, Pro Yearly, Team Monthly, Team Yearly]
        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()

        # Can not do Team plan when at 11 activated users
        assert self.plan_service.available_plans(owner=self.owner) == expected_result

    @patch("services.sentry.is_sentry_user")
    def test_sentry_user(self, is_sentry_user):
        is_sentry_user.return_value = True

        # [Basic, Pro Monthly, Pro Yearly, Sentry Monthly, Sentry Yearly, Team Monthly, Team Yearly]
        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += SENTRY_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += TEAM_PLAN_REPRESENTATIONS.values()

        # Can do Team plan when plan_activated_users is null
        assert self.plan_service.available_plans(owner=self.owner) == expected_result

        self.current_org.plan_activated_users = [i for i in range(10)]
        self.current_org.save()

        # Can do Team plan when at 10 activated users
        assert self.plan_service.available_plans(owner=self.owner) == expected_result

        self.current_org.plan_activated_users = [i for i in range(11)]
        self.current_org.save()

        # [Basic, Pro Monthly, Pro Yearly, Sentry Monthly, Sentry Yearly]
        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += SENTRY_PAID_USER_PLAN_REPRESENTATIONS.values()

        # Can not do Team plan when at 11 activated users
        assert self.plan_service.available_plans(owner=self.owner) == expected_result
