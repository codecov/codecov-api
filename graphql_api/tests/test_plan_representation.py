from datetime import timedelta

from django.test import TransactionTestCase
from django.utils import timezone
from freezegun import freeze_time
from shared.django_apps.core.tests.factories import OwnerFactory
from shared.plan.constants import PlanName, TrialStatus

from .helper import GraphQLTestHelper


class TestPlanRepresentationsType(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.current_org = OwnerFactory(
            username="random-plan-user",
            service="github",
            trial_start_date=timezone.now(),
            trial_end_date=timezone.now() + timedelta(days=14),
        )

    @freeze_time("2023-06-19")
    def test_owner_pretrial_plan_data_when_trialing(self):
        now = timezone.now()
        later = timezone.now() + timedelta(days=14)
        current_org = OwnerFactory(
            username="random-plan-user",
            service="github",
            plan=PlanName.TRIAL_PLAN_NAME.value,
            trial_start_date=now,
            trial_end_date=later,
            trial_status=TrialStatus.ONGOING.value,
            pretrial_users_count=234,
        )
        query = """{
            owner(username: "%s") {
                pretrialPlan {
                    marketingName
                    planName
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
            "marketingName": "Developer",
            "planName": "users-basic",
            "value": "users-basic",
            "billingRate": None,
            "baseUnitPrice": 0,
            "benefits": [
                "Up to 234 users",
                "Unlimited public repositories",
                "Unlimited private repositories",
            ],
            "monthlyUploadLimit": 250,
        }
