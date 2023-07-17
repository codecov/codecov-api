from datetime import timedelta

from django.test import TransactionTestCase
from django.utils import timezone
from freezegun import freeze_time

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import OwnerFactory

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
    def test_owner_plan_data(self):
        current_org = OwnerFactory(
            username="random-plan-user",
            service="github",
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
        data = self.gql_request(query, user=current_org)
        assert data["owner"]["plan"] == {
            "trialStatus": "ONGOING",
            "trialEndDate": "2023-07-03T00:00:00",
            "trialStartDate": "2023-06-19T00:00:00",
            "marketingName": "Developer",
            "planName": "users-basic",
            "billingRate": None,
            "baseUnitPrice": 0,
            "benefits": [
                "Up to 1 user",
                "Unlimited public repositories",
                "Unlimited private repositories",
            ],
            "monthlyUploadLimit": None,
        }
