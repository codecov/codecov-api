from datetime import timedelta

from django.test import TransactionTestCase
from django.utils import timezone
from freezegun import freeze_time

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import OwnerFactory
from plan.constants import PlanName

from .helper import GraphQLTestHelper


class TestOwnerType(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.current_org = OwnerFactory(
            username="random-plan-user",
            service="github",
            trial_start_date=timezone.now(),
            trial_end_date=timezone.now() + timedelta(days=14),
        )

    @freeze_time("2023-06-19")
    def test_owner_plan_data_when_trialing(self):
        current_org = OwnerFactory(
            username="random-plan-user",
            service="github",
            plan=PlanName.TRIAL_PLAN_NAME.value,
            trial_start_date=timezone.now(),
            trial_end_date=timezone.now() + timedelta(days=14),
        )
        query = """{
            owner(username: "%s") {
                plan {
                    trialStatus
                    trialEndDate
                    trialStartDate
                    marketingName
                    planName
                    billingRate
                    baseUnitPrice
                    benefits
                    monthlyUploadLimit
                }
            }
        }
        """ % (
            current_org.username
        )
        data = self.gql_request(query, owner=current_org)
        assert data["owner"]["plan"] == {
            "trialStatus": "ONGOING",
            "trialEndDate": "2023-07-03T00:00:00",
            "trialStartDate": "2023-06-19T00:00:00",
            "marketingName": "Developer",
            "planName": "users-trial",
            "billingRate": None,
            "baseUnitPrice": 0,
            "benefits": [
                "Configurable # of users",
                "Unlimited public repositories",
                "Unlimited private repositories",
                "Priority Support",
            ],
            "monthlyUploadLimit": None,
        }
