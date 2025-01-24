from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from django.test import TransactionTestCase
from django.utils import timezone
from freezegun import freeze_time
from shared.django_apps.codecov_auth.tests.factories import AccountFactory
from shared.django_apps.core.tests.factories import OwnerFactory
from shared.license import LicenseInformation
from shared.plan.constants import PlanName, TrialStatus
from shared.utils.test_utils import mock_config_helper

from billing.helpers import mock_all_plans_and_tiers

from .helper import GraphQLTestHelper


class TestPlanType(GraphQLTestHelper, TransactionTestCase):
    @pytest.fixture(scope="function", autouse=True)
    def inject_mocker(request, mocker):
        request.mocker = mocker

    def setUp(self):
        mock_all_plans_and_tiers()
        self.current_org = OwnerFactory(
            username="random-plan-user",
            service="github",
            trial_start_date=timezone.now(),
            trial_end_date=timezone.now() + timedelta(days=14),
        )

    @freeze_time("2023-06-19")
    def test_owner_plan_data_when_trialing(self):
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
            plan_user_count=123,
        )
        query = """{
            owner(username: "%s") {
                plan {
                    trialStatus
                    trialEndDate
                    trialStartDate
                    trialTotalDays
                    marketingName
                    value
                    tierName
                    billingRate
                    baseUnitPrice
                    benefits
                    monthlyUploadLimit
                    pretrialUsersCount
                    planUserCount
                    isEnterprisePlan
                    isFreePlan
                    isProPlan
                    isSentryPlan
                    isTeamPlan
                    isTrialPlan
                }
            }
        }
        """ % (current_org.username)
        data = self.gql_request(query, owner=current_org)
        assert data["owner"]["plan"] == {
            "trialStatus": "ONGOING",
            "trialEndDate": "2023-07-03T00:00:00",
            "trialStartDate": "2023-06-19T00:00:00",
            "trialTotalDays": 14,
            "marketingName": "Developer",
            "value": "users-trial",
            "tierName": "trial",
            "billingRate": None,
            "baseUnitPrice": 0,
            "benefits": [
                "Configurable # of users",
                "Unlimited public repositories",
                "Unlimited private repositories",
                "Priority Support",
            ],
            "monthlyUploadLimit": None,
            "pretrialUsersCount": 234,
            "planUserCount": 123,
            "isEnterprisePlan": False,
            "isFreePlan": False,
            "isProPlan": False,
            "isSentryPlan": False,
            "isTeamPlan": False,
            "isTrialPlan": True,
        }

    def test_owner_plan_data_with_account(self):
        self.current_org.account = AccountFactory(
            plan=PlanName.CODECOV_PRO_YEARLY.value,
            plan_seat_count=25,
        )
        self.current_org.save()
        query = """{
                owner(username: "%s") {
                    plan {
                        marketingName
                        value
                        tierName
                        billingRate
                        baseUnitPrice
                        planUserCount
                        isEnterprisePlan
                        isFreePlan
                        isProPlan
                        isSentryPlan
                        isTeamPlan
                        isTrialPlan
                    }
                }
            }
            """ % (self.current_org.username)
        data = self.gql_request(query, owner=self.current_org)
        assert data["owner"]["plan"] == {
            "marketingName": "Pro",
            "value": "users-pr-inappy",
            "tierName": "pro",
            "billingRate": "annually",
            "baseUnitPrice": 10,
            "planUserCount": 25,
            "isEnterprisePlan": False,
            "isFreePlan": False,
            "isProPlan": True,
            "isSentryPlan": False,
            "isTeamPlan": False,
            "isTrialPlan": False,
        }

    def test_owner_plan_data_has_seats_left(self):
        current_org = OwnerFactory(
            username="random-plan-user",
            service="github",
            plan=PlanName.TRIAL_PLAN_NAME.value,
            trial_status=TrialStatus.ONGOING.value,
            plan_user_count=2,
            plan_activated_users=[],
        )
        query = """{
            owner(username: "%s") {
                plan {
                    hasSeatsLeft
                }
            }
        }
        """ % (current_org.username)
        data = self.gql_request(query, owner=current_org)
        assert data["owner"]["plan"] == {"hasSeatsLeft": True}

    @patch("shared.self_hosted.service.get_current_license")
    def test_plan_user_count_for_enterprise_org(self, mocked_license):
        """
        If an Org has an enterprise license, number_allowed_users from their license
        should be used instead of plan_user_count on the Org object.
        """
        mock_enterprise_license = LicenseInformation(
            is_valid=True,
            message=None,
            url="https://codeov.mysite.com",
            number_allowed_users=5,
            number_allowed_repos=10,
            expires=datetime.strptime("2020-05-09 00:00:00", "%Y-%m-%d %H:%M:%S"),
            is_trial=False,
            is_pr_billing=True,
        )
        mocked_license.return_value = mock_enterprise_license
        mock_config_helper(
            self.mocker, configs={"setup.enterprise_license": mock_enterprise_license}
        )

        enterprise_org = OwnerFactory(
            username="random-plan-user",
            service="github",
            plan=PlanName.CODECOV_PRO_YEARLY.value,
            plan_user_count=1,
            plan_activated_users=[],
        )
        for i in range(4):
            new_owner = OwnerFactory()
            enterprise_org.plan_activated_users.append(new_owner.ownerid)
        enterprise_org.save()

        other_org_in_enterprise = OwnerFactory(
            service="github",
            plan=PlanName.CODECOV_PRO_YEARLY.value,
            plan_user_count=1,
            plan_activated_users=[],
        )
        for i in range(4):
            new_owner = OwnerFactory()
            other_org_in_enterprise.plan_activated_users.append(new_owner.ownerid)
        other_org_in_enterprise.save()

        query = """{
                    owner(username: "%s") {
                        plan {
                            planUserCount
                            hasSeatsLeft
                        }
                    }
                }
                """ % (enterprise_org.username)
        data = self.gql_request(query, owner=enterprise_org)
        assert data["owner"]["plan"]["planUserCount"] == 5
        assert data["owner"]["plan"]["hasSeatsLeft"] == False

    @patch("shared.self_hosted.service.get_current_license")
    def test_plan_user_count_for_enterprise_org_invaild_license(self, mocked_license):
        mock_enterprise_license = LicenseInformation(
            is_valid=False,
        )
        mocked_license.return_value = mock_enterprise_license
        mock_config_helper(
            self.mocker, configs={"setup.enterprise_license": mock_enterprise_license}
        )

        enterprise_org = OwnerFactory(
            username="random-plan-user",
            service="github",
            plan=PlanName.CODECOV_PRO_YEARLY.value,
            plan_user_count=1,
            plan_activated_users=[],
        )
        query = """{
                        owner(username: "%s") {
                            plan {
                                planUserCount
                                hasSeatsLeft
                            }
                        }
                    }
                    """ % (enterprise_org.username)
        data = self.gql_request(query, owner=enterprise_org)
        assert data["owner"]["plan"]["planUserCount"] == 0
        assert data["owner"]["plan"]["hasSeatsLeft"] == False

    def test_owner_plan_data_when_trial_status_is_none(self):
        now = timezone.now()
        later = now + timedelta(days=14)
        current_org = OwnerFactory(
            username="random-plan-user",
            service="github",
            plan=PlanName.TRIAL_PLAN_NAME.value,
            trial_start_date=now,
            trial_end_date=later,
            trial_status=None,
        )
        query = """{
            owner(username: "%s") {
                plan {
                    trialStatus
                }
            }
        }
        """ % (current_org.username)
        data = self.gql_request(query, owner=current_org)
        assert data["owner"]["plan"]["trialStatus"] == "NOT_STARTED"
