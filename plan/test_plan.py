from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TestCase
from freezegun import freeze_time

from codecov.commands.exceptions import ValidationError
from codecov_auth.tests.factories import OwnerFactory
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
        assert current_org_with_ongoing_trial.plan_activated_users == None
        assert current_org_with_ongoing_trial.plan_user_count == 1
        assert current_org_with_ongoing_trial.trial_end_date == datetime.utcnow()

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
        assert current_org_with_ongoing_trial.trial_end_date == datetime.utcnow()

    def test_plan_service_expire_trial_users_pretrial_users_count_if_existing(
        self,
    ):
        trial_start_date = datetime.utcnow()
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
        assert current_org_with_ongoing_trial.plan_activated_users == None
        assert current_org_with_ongoing_trial.plan_user_count == pretrial_users_count
        assert current_org_with_ongoing_trial.trial_end_date == datetime.utcnow()

    def test_plan_service_start_trial_errors_if_status_is_ongoing(self):
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
        current_owner = OwnerFactory()

        with self.assertRaises(ValidationError) as e:
            plan_service.start_trial(current_owner=current_owner)

    def test_plan_service_start_trial_errors_if_status_is_expired(self):
        trial_start_date = datetime.utcnow()
        trial_end_date = trial_start_date + timedelta(days=-1)
        current_org = OwnerFactory(
            plan=PlanName.BASIC_PLAN_NAME.value,
            trial_start_date=trial_start_date,
            trial_end_date=trial_end_date,
            trial_status=TrialStatus.EXPIRED.value,
        )
        plan_service = PlanService(current_org=current_org)
        current_owner = OwnerFactory()

        with self.assertRaises(ValidationError) as e:
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

        with self.assertRaises(ValidationError) as e:
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

        with self.assertRaises(ValidationError) as e:
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
        assert current_org.trial_start_date == datetime.utcnow()
        assert current_org.trial_end_date == datetime.utcnow() + timedelta(
            days=TrialDaysAmount.CODECOV_SENTRY.value
        )
        assert current_org.trial_status == TrialStatus.ONGOING.value
        assert current_org.plan == PlanName.TRIAL_PLAN_NAME.value
        assert current_org.pretrial_users_count == plan_user_count
        assert current_org.plan_user_count == TRIAL_PLAN_SEATS
        assert current_org.plan_auto_activate == True
        assert current_org.trial_fired_by == current_owner.ownerid

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
        assert plan_service.tier_name == trial_plan.tier_name
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

    def test_plan_service_returns_if_owner_has_trial_dates(self):
        current_org = OwnerFactory(
            plan=PlanName.CODECOV_PRO_MONTHLY.value,
            trial_start_date=datetime.utcnow(),
            trial_end_date=datetime.utcnow() + timedelta(days=14),
        )
        current_org.save()

        plan_service = PlanService(current_org=current_org)

        assert plan_service.has_trial_dates == True


class AvailablePlansBeforeTrial(TestCase):
    """
    - users-basic, no trial -> users-pr-inappm/y, users-basic
    - users-free, no trial -> users-pr-inappm/y, users-basic, users-free
    - users-litem/y, no trial -> users-pr-inappm/y, users-basic, users-litem/y
    - users-pr-inappm/y, no trial -> users-pr-inappm/y, users-basic
    - sentry customer, users-basic, no trial -> users-pr-inappm/y, users-sentrym/y, users-basic
    - sentry customer, users-litem/y, no trial -> users-pr-inappm/y, users-sentrym/y, users-basic, users-litem/y
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

        assert plan_service.available_plans(owner=self.owner) == expected_result

    def test_available_plans_for_lite_plan_non_trial(
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

        assert plan_service.available_plans(owner=self.owner) == expected_result

    @patch("services.sentry.is_sentry_user")
    def test_available_plans_for_sentry_customer_lite_plan_non_trial(
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

        assert plan_service.available_plans(owner=self.owner) == expected_result


@freeze_time("2023-06-19")
class AvailablePlansExpiredTrialLessThanTenUsers(TestCase):
    """
    - users-basic, has trialed, less than 10 users -> users-pr-inappm/y, users-basic, users-litem/y
    - users-litem/y, has trialed, less than 10 users -> users-pr-inappm/y, users-basic, users-litem/y
    - users-pr-inappm/y, has trialed, less than 10 users -> users-pr-inappm/y, users-basic, users-litem/y
    - sentry customer, users-basic, has trialed, less than 10 users -> users-pr-inappm/y, users-sentrym/y, users-basic, users-litem/y
    - sentry customer, users-litem/y, has trialed, less than 10 users -> users-pr-inappm/y, users-sentrym/y, users-basic, users-litem/y
    - sentry customer, users-sentrym/y, has trialed, less than 10 users -> users-pr-inappm/y, users-sentrym/y, users-basic, users-litem/y
    """

    def setUp(self):
        self.current_org = OwnerFactory(
            trial_start_date=datetime.utcnow() + timedelta(days=-10),
            trial_end_date=datetime.utcnow() + timedelta(days=-3),
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

    def test_available_plans_for_lite_plan_expired_trial_less_than_10_users(
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
    def test_available_plans_for_sentry_customer_lite_plan_expired_trial_less_than_10_users(
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
class AvailablePlansExpiredTrialMoreThanTenUsers(TestCase):
    """
    - users-pr-inappm/y, has trialed, more than 10 users -> users-pr-inappm/y, users-basic
    - sentry customer, users-basic, has trialed, more than 10 users -> users-pr-inappm/y, users-sentrym/y, users-basic
    - sentry customer, users-sentrym/y, has trialed, more than 10 users -> users-pr-inappm/y, users-sentrym/y, users-basic
    """

    def setUp(self):
        self.current_org = OwnerFactory(
            trial_start_date=datetime.utcnow() + timedelta(days=-10),
            trial_end_date=datetime.utcnow() + timedelta(days=-3),
            trial_status=TrialStatus.EXPIRED.value,
            plan_user_count=13,
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
class AvailablePlansOngoingTrialMoreThanTenUsers(TestCase):
    """
    - users-trial, is trialing, more than 10 users -> users-pr-inappm/y, users-basic
    - sentry-customer, users-trial, is trialing, more than 10 users -> users-pr-inappm/y, users-sentrym/y, users-basic
    """

    def setUp(self):
        self.current_org = OwnerFactory(
            trial_start_date=datetime.utcnow(),
            trial_end_date=datetime.utcnow() + timedelta(days=14),
            trial_status=TrialStatus.ONGOING.value,
            plan_user_count=13,
        )
        self.owner = OwnerFactory()

    def test_available_plans_for_users_trial_plan_ongoing_trial_more_than_10_seats(
        self,
    ):
        self.current_org.plan = PlanName.TRIAL_PLAN_NAME.value
        self.current_org.save()

        plan_service = PlanService(current_org=self.current_org)

        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += TEAM_PLAN_REPRESENTATIONS.values()

        assert plan_service.available_plans(owner=self.owner) == expected_result

    @patch("services.sentry.is_sentry_user")
    def test_available_plans_for_sentry_customer_users_trial_plan_ongoing_trial_more_than_10_seats(
        self, is_sentry_user
    ):
        is_sentry_user.return_value = True
        self.current_org.plan = PlanName.TRIAL_PLAN_NAME.value
        self.current_org.save()

        plan_service = PlanService(current_org=self.current_org)

        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += SENTRY_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += TEAM_PLAN_REPRESENTATIONS.values()

        assert plan_service.available_plans(owner=self.owner) == expected_result

    def test_available_plans_for_more_than_10_activated_users(self):
        self.current_org.plan = PlanName.TRIAL_PLAN_NAME.value
        self.current_org.save()

        plan_service = PlanService(current_org=self.current_org)

        # [Basic, Pro Monthly, Pro Yearly, Team Monthly, Team Yearly]
        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += TEAM_PLAN_REPRESENTATIONS.values()

        # Can do Team plan when plan_activated_users is null
        assert plan_service.available_plans(owner=self.owner) == expected_result

        self.current_org.plan_activated_users = [i for i in range(10)]
        self.current_org.save()

        # Can do Team plan when at 10 activated users
        assert plan_service.available_plans(owner=self.owner) == expected_result

        self.current_org.plan_activated_users = [i for i in range(11)]
        self.current_org.save()

        # Can not do Team plan when at 11 activated users
        assert plan_service.available_plans(owner=self.owner) == expected_result[:3]

@freeze_time("2023-06-19")
class AvailablePlansOngoingTrialLessThanTenUsers(TestCase):
    """
    - users-trial, is trialing, less than 10 users -> users-pr-inappm/y, users-basic, users-litem/y
    - sentry-customer, users-trial, is trialing, less than 10 users -> users-pr-inappm/y, users-sentrym/y, users-basic, users-litem/y
    """

    def setUp(self):
        self.current_org = OwnerFactory(
            trial_start_date=datetime.utcnow(),
            trial_end_date=datetime.utcnow() + timedelta(days=14),
            trial_status=TrialStatus.ONGOING.value,
            plan_user_count=3,
        )
        self.owner = OwnerFactory()

    def test_available_plans_for_users_trial_plan_ongoing_trial_less_than_10_users(
        self,
    ):
        self.current_org.plan = PlanName.TRIAL_PLAN_NAME.value
        self.current_org.save()

        plan_service = PlanService(current_org=self.current_org)

        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += TEAM_PLAN_REPRESENTATIONS.values()

        assert plan_service.available_plans(owner=self.owner) == expected_result

    @patch("services.sentry.is_sentry_user")
    def test_available_plans_for_sentry_customer_users_trial_plan_ongoing_trial_less_than_10_users(
        self, is_sentry_user
    ):
        is_sentry_user.return_value = True
        self.current_org.plan = PlanName.TRIAL_PLAN_NAME.value
        self.current_org.save()

        plan_service = PlanService(current_org=self.current_org)

        expected_result = []
        expected_result.append(BASIC_PLAN)
        expected_result += PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += SENTRY_PAID_USER_PLAN_REPRESENTATIONS.values()
        expected_result += TEAM_PLAN_REPRESENTATIONS.values()

        assert plan_service.available_plans(owner=self.owner) == expected_result
