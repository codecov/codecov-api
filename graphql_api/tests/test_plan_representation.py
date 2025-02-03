from datetime import timedelta

from django.test import TransactionTestCase
from django.utils import timezone
from freezegun import freeze_time
from shared.django_apps.codecov_auth.tests.factories import PlanFactory, TierFactory
from shared.django_apps.core.tests.factories import OwnerFactory
from shared.plan.constants import PlanName, TierName, TrialStatus

from .helper import GraphQLTestHelper


class TestPlanRepresentationsType(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.tier = TierFactory(tier_name=TierName.BASIC.value)
        self.plan = PlanFactory(tier=self.tier, is_active=True)
        self.current_org = OwnerFactory(
            username="random-plan-user",
            service="github",
            trial_start_date=timezone.now(),
            trial_end_date=timezone.now() + timedelta(days=14),
            plan=self.plan.name,
        )

    @freeze_time("2023-06-19")
    def test_owner_pretrial_plan_data_when_trialing(self):
        now = timezone.now()
        later = timezone.now() + timedelta(days=14)
        trial_tier = TierFactory(tier_name=TierName.TRIAL.value)
        trial_plan = PlanFactory(
            tier=trial_tier,
            is_active=True,
            name=PlanName.TRIAL_PLAN_NAME.value,
        )
        current_org = OwnerFactory(
            username="random-plan-user",
            service="github",
            plan=trial_plan.name,
            trial_start_date=now,
            trial_end_date=later,
            trial_status=TrialStatus.ONGOING.value,
            pretrial_users_count=234,
        )
        query = """{
            owner(username: "%s") {
                pretrialPlan {
                    marketingName
                    value
                    billingRate
                    baseUnitPrice
                    benefits
                    monthlyUploadLimit
                }
            }
        }
        """ % (current_org.username)
        data = self.gql_request(query, owner=current_org)
        assert data["owner"]["pretrialPlan"] == {
            "marketingName": self.plan.marketing_name,
            "value": "users-basic",
            "billingRate": None,
            "baseUnitPrice": 0,
            "benefits": ["Benefit 1", "Benefit 2", "Benefit 3"],
            "monthlyUploadLimit": None,
        }
