import json
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from shared.django_apps.codecov_auth.tests.factories import (
    AccountFactory,
    InvoiceBillingFactory,
    OwnerFactory,
    UserFactory,
)
from shared.plan.constants import DEFAULT_FREE_PLAN, PlanName, TrialStatus
from stripe import StripeError

from api.internal.tests.test_utils import GetAdminProviderAdapter
from billing.helpers import mock_all_plans_and_tiers
from codecov_auth.models import Service
from utils.test_utils import APIClient

curr_path = os.path.dirname(__file__)


class MockSubscription(object):
    def __init__(self, subscription_params: dict):
        self.items = {"data": [{"id": "abc"}]}
        self.cancel_at_period_end = False
        self.current_period_end = 1633512445
        self.latest_invoice = subscription_params.get(
            "latest_invoice",
            {
                "id": "in_123",
                "status": "complete",
            },
        )

        default_payment_method = {
            "id": "pm_123",
            "card": {
                "brand": "visa",
                "exp_month": 12,
                "exp_year": 2024,
                "last4": "abcd",
            },
        }
        self.customer = {
            "invoice_settings": {
                "default_payment_method": subscription_params.get(
                    "default_payment_method", default_payment_method
                )
            },
            "id": "cus_LK&*Hli8YLIO",
            "discount": None,
            "email": None,
        }
        self.schedule = subscription_params.get("schedule_id")
        self.status = subscription_params.get("status", "active")
        self.collection_method = subscription_params.get(
            "collection_method", "charge_automatically"
        )
        self.trial_end = subscription_params.get("trial_end")

        customer_coupon = subscription_params.get("customer_coupon")
        if customer_coupon:
            self.customer["discount"] = {"coupon": customer_coupon}

        pending_update = subscription_params.get("pending_update")
        if pending_update:
            self.pending_update = pending_update

    def __getitem__(self, key):
        return getattr(self, key)


class MockMetadata(object):
    def __init__(self):
        self.obo = 2
        self.obo_organization = 3

    def __getitem__(self, key):
        return getattr(self, key)


class MockSchedule(object):
    def __init__(self, schedule_params, phases):
        self.id = schedule_params["id"]
        self.phases = phases
        self.metadata = MockMetadata()

    def __getitem__(self, key):
        return getattr(self, key)


@pytest.mark.usefixtures("codecov_vcr")
class AccountViewSetTests(APITestCase):
    def _retrieve(self, kwargs={}):
        if not kwargs:
            kwargs = {
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            }
        return self.client.get(reverse("account_details-detail", kwargs=kwargs))

    def _update(self, kwargs, data):
        return self.client.patch(
            reverse("account_details-detail", kwargs=kwargs), data=data, format="json"
        )

    def _destroy(self, kwargs):
        return self.client.delete(reverse("account_details-detail", kwargs=kwargs))

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_all_plans_and_tiers()

    def setUp(self):
        self.service = "gitlab"
        self.current_owner = OwnerFactory(
            stripe_customer_id=1000,
            service=Service.GITHUB.value,
            service_id="10238974029348",
        )
        self.expected_invoice = {
            "number": "EF0A41E-0001",
            "status": "paid",
            "id": "in_19yTU92eZvKYlo2C7uDjvu6v",
            "created": 1489789429,
            "period_start": 1487370220,
            "period_end": 1489789420,
            "due_date": None,
            "customer_name": "Peer Company",
            "customer_address": "6639 Boulevard Dr, Westwood FL 34202 USA",
            "currency": "usd",
            "amount_paid": 999,
            "amount_due": 999,
            "amount_remaining": 0,
            "total": 999,
            "subtotal": 999,
            "invoice_pdf": "https://pay.stripe.com/invoice/acct_1032D82eZvKYlo2C/invst_a7KV10HpLw2QxrihgVyuOkOjMZ/pdf",
            "line_items": [
                {
                    "description": "(10) users-pr-inappm",
                    "amount": 120,
                    "currency": "usd",
                    "plan_name": PlanName.CODECOV_PRO_MONTHLY.value,
                    "quantity": 1,
                    "period": {"end": 1521326190, "start": 1518906990},
                }
            ],
            "footer": None,
            "customer_email": "olivia.williams.03@example.com",
            "customer_shipping": None,
        }

        self.client = APIClient()
        self.client.force_login_owner(self.current_owner)

    def test_retrieve_own_account_give_200(self):
        response = self._retrieve(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            }
        )
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_account_gets_account_fields(self):
        owner = OwnerFactory(admins=[self.current_owner.ownerid])
        self.current_owner.organizations = [owner.ownerid]
        self.current_owner.save()
        response = self._retrieve(
            kwargs={"service": owner.service, "owner_username": owner.username}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "activated_user_count": 0,
            "root_organization": None,
            "integration_id": owner.integration_id,
            "plan_auto_activate": owner.plan_auto_activate,
            "inactive_user_count": 1,
            "plan": {
                "marketing_name": "Developer",
                "value": DEFAULT_FREE_PLAN,
                "billing_rate": None,
                "base_unit_price": 0,
                "benefits": [
                    "Up to 1 user",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                ],
                "quantity": 1,
            },
            "subscription_detail": None,
            "checkout_session_id": None,
            "name": owner.name,
            "email": owner.email,
            "nb_active_private_repos": 0,
            "repo_total_credits": 99999999,
            "plan_provider": owner.plan_provider,
            "activated_student_count": 0,
            "student_count": 0,
            "schedule_detail": None,
            "uses_invoice": False,
            "delinquent": None,
        }

    @patch("services.billing.stripe.SubscriptionSchedule.retrieve")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_retrieve_account_gets_account_fields_when_there_are_scheduled_details(
        self, mock_retrieve_subscription, mock_retrieve_schedule
    ):
        owner = OwnerFactory(
            admins=[self.current_owner.ownerid], stripe_subscription_id="sub_123"
        )
        self.current_owner.organizations = [owner.ownerid]
        self.current_owner.save()

        subscription_params = {
            "default_payment_method": None,
            "cancel_at_period_end": False,
            "current_period_end": 1633512445,
            "latest_invoice": None,
            "schedule_id": "sub_sched_456",
            "collection_method": "charge_automatically",
            "tax_ids": None,
        }

        mock_retrieve_subscription.return_value = MockSubscription(subscription_params)
        schedule_params = {
            "id": 123,
            "start_date": 123689126736,
            "stripe_plan_id": "plan_pro_yearly",
            "quantity": 6,
        }
        phases = [
            {},
            {
                "start_date": schedule_params["start_date"],
                "items": [
                    {
                        "plan": schedule_params["stripe_plan_id"],
                        "quantity": schedule_params["quantity"],
                    }
                ],
            },
        ]

        mock_retrieve_schedule.return_value = MockSchedule(schedule_params, phases)

        response = self._retrieve(
            kwargs={"service": owner.service, "owner_username": owner.username}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "integration_id": owner.integration_id,
            "activated_student_count": 0,
            "activated_user_count": 0,
            "checkout_session_id": None,
            "delinquent": None,
            "email": owner.email,
            "inactive_user_count": 1,
            "name": owner.name,
            "nb_active_private_repos": 0,
            "plan_auto_activate": True,
            "plan_provider": owner.plan_provider,
            "plan": {
                "marketing_name": "Developer",
                "value": DEFAULT_FREE_PLAN,
                "billing_rate": None,
                "base_unit_price": 0,
                "benefits": [
                    "Up to 1 user",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                ],
                "quantity": 1,
            },
            "repo_total_credits": 99999999,
            "root_organization": None,
            "schedule_detail": {
                "id": "123",
                "scheduled_phase": {
                    "start_date": schedule_params["start_date"],
                    "plan": "Pro",
                    "quantity": schedule_params["quantity"],
                },
            },
            "student_count": 0,
            "subscription_detail": {
                "latest_invoice": None,
                "default_payment_method": None,
                "cancel_at_period_end": False,
                "current_period_end": 1633512445,
                "customer": {"id": "cus_LK&*Hli8YLIO", "discount": None, "email": None},
                "collection_method": "charge_automatically",
                "tax_ids": None,
                "trial_end": None,
            },
            "uses_invoice": False,
        }

    @patch("services.billing.stripe.SubscriptionSchedule.retrieve")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_retrieve_account_returns_last_phase_when_more_than_one_scheduled_phases(
        self, mock_retrieve_subscription, mock_retrieve_schedule
    ):
        owner = OwnerFactory(
            admins=[self.current_owner.ownerid], stripe_subscription_id="sub_2345687"
        )
        self.current_owner.organizations = [owner.ownerid]
        self.current_owner.save()

        subscription_params = {
            "default_payment_method": None,
            "cancel_at_period_end": False,
            "current_period_end": 1633512445,
            "latest_invoice": None,
            "schedule_id": "sub_sched_456678999",
            "collection_method": "charge_automatically",
            "trial_end": 1633512445,
            "tax_ids": None,
        }

        mock_retrieve_subscription.return_value = MockSubscription(subscription_params)
        schedule_params = {
            "id": 123,
            "start_date": 123689126736,
            "stripe_plan_id": "plan_pro_yearly",
            "quantity": 6,
        }
        phases = [
            {
                "start_date": 123689126536,
                "items": [{"plan": "test_plan_123", "quantity": 4}],
            },
            {
                "start_date": 123689126636,
                "items": [{"plan": "test_plan_456", "quantity": 5}],
            },
            {
                "start_date": schedule_params["start_date"],
                "items": [
                    {
                        "plan": schedule_params["stripe_plan_id"],
                        "quantity": schedule_params["quantity"],
                    }
                ],
            },
        ]

        mock_retrieve_schedule.return_value = MockSchedule(schedule_params, phases)

        response = self._retrieve(
            kwargs={"service": owner.service, "owner_username": owner.username}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "activated_user_count": 0,
            "root_organization": None,
            "integration_id": owner.integration_id,
            "plan_auto_activate": owner.plan_auto_activate,
            "inactive_user_count": 1,
            "plan": {
                "marketing_name": "Developer",
                "value": DEFAULT_FREE_PLAN,
                "billing_rate": None,
                "base_unit_price": 0,
                "benefits": [
                    "Up to 1 user",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                ],
                "quantity": 1,
            },
            "subscription_detail": {
                "latest_invoice": None,
                "default_payment_method": None,
                "cancel_at_period_end": False,
                "current_period_end": 1633512445,
                "customer": {"id": "cus_LK&*Hli8YLIO", "discount": None, "email": None},
                "collection_method": "charge_automatically",
                "trial_end": 1633512445,
                "tax_ids": None,
            },
            "checkout_session_id": None,
            "name": owner.name,
            "email": owner.email,
            "nb_active_private_repos": 0,
            "repo_total_credits": 99999999,
            "plan_provider": owner.plan_provider,
            "activated_student_count": 0,
            "student_count": 0,
            "schedule_detail": {
                "id": "123",
                "scheduled_phase": {
                    "plan": "Pro",
                    "quantity": schedule_params["quantity"],
                    "start_date": schedule_params["start_date"],
                },
            },
            "uses_invoice": False,
            "delinquent": None,
        }

    @patch("services.billing.stripe.Subscription.retrieve")
    def test_retrieve_account_gets_none_for_schedule_details_when_schedule_is_nonexistent(
        self, mock_retrieve_subscription
    ):
        owner = OwnerFactory(
            admins=[self.current_owner.ownerid], stripe_subscription_id="sub_123"
        )
        self.current_owner.organizations = [owner.ownerid]
        self.current_owner.save()

        subscription_params = {
            "default_payment_method": None,
            "cancel_at_period_end": False,
            "current_period_end": 1633512445,
            "latest_invoice": None,
            "schedule_id": None,
            "collection_method": "charge_automatically",
            "tax_ids": None,
        }

        mock_retrieve_subscription.return_value = MockSubscription(subscription_params)

        response = self._retrieve(
            kwargs={"service": owner.service, "owner_username": owner.username}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "activated_user_count": 0,
            "root_organization": None,
            "integration_id": owner.integration_id,
            "plan_auto_activate": owner.plan_auto_activate,
            "inactive_user_count": 1,
            "plan": {
                "marketing_name": "Developer",
                "value": DEFAULT_FREE_PLAN,
                "billing_rate": None,
                "base_unit_price": 0,
                "benefits": [
                    "Up to 1 user",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                ],
                "quantity": 1,
            },
            "subscription_detail": {
                "latest_invoice": None,
                "default_payment_method": None,
                "cancel_at_period_end": False,
                "current_period_end": 1633512445,
                "customer": {"id": "cus_LK&*Hli8YLIO", "discount": None, "email": None},
                "collection_method": "charge_automatically",
                "trial_end": None,
                "tax_ids": None,
            },
            "checkout_session_id": None,
            "name": owner.name,
            "email": owner.email,
            "nb_active_private_repos": 0,
            "repo_total_credits": 99999999,
            "plan_provider": owner.plan_provider,
            "activated_student_count": 0,
            "student_count": 0,
            "schedule_detail": None,
            "uses_invoice": False,
            "delinquent": None,
        }

    def test_retrieve_account_gets_account_students(self):
        owner = OwnerFactory(
            admins=[self.current_owner.ownerid],
            plan_activated_users=[OwnerFactory(student=True).ownerid],
        )
        self.current_owner.organizations = [owner.ownerid]
        self.current_owner.save()
        OwnerFactory(organizations=[owner.ownerid], student=True)
        OwnerFactory(organizations=[owner.ownerid], student=True)
        response = self._retrieve(
            kwargs={"service": owner.service, "owner_username": owner.username}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "activated_user_count": 0,
            "root_organization": None,
            "integration_id": owner.integration_id,
            "plan_auto_activate": owner.plan_auto_activate,
            "inactive_user_count": 1,
            "plan": response.data["plan"],
            "subscription_detail": None,
            "checkout_session_id": None,
            "name": owner.name,
            "email": owner.email,
            "nb_active_private_repos": 0,
            "repo_total_credits": 99999999,
            "plan_provider": owner.plan_provider,
            "activated_student_count": 1,
            "student_count": 3,
            "schedule_detail": None,
            "uses_invoice": False,
            "delinquent": None,
        }

    def test_account_with_free_user_plan(self):
        self.current_owner.plan = DEFAULT_FREE_PLAN
        self.current_owner.save()
        response = self._retrieve()
        assert response.status_code == status.HTTP_200_OK
        assert response.data["plan"] == {
            "marketing_name": "Developer",
            "value": DEFAULT_FREE_PLAN,
            "billing_rate": None,
            "base_unit_price": 0,
            "benefits": [
                "Up to 1 user",
                "Unlimited public repositories",
                "Unlimited private repositories",
            ],
            "quantity": self.current_owner.plan_user_count,
        }

    def test_account_with_paid_user_plan_billed_monthly(self):
        self.current_owner.plan = PlanName.CODECOV_PRO_MONTHLY.value
        self.current_owner.save()
        response = self._retrieve()
        assert response.status_code == status.HTTP_200_OK
        assert response.data["plan"] == {
            "marketing_name": "Pro",
            "value": PlanName.CODECOV_PRO_MONTHLY.value,
            "billing_rate": "monthly",
            "base_unit_price": 12,
            "benefits": [
                "Configurable # of users",
                "Unlimited public repositories",
                "Unlimited private repositories",
                "Priority Support",
            ],
            "quantity": self.current_owner.plan_user_count,
        }

    def test_account_with_paid_user_plan_billed_annually(self):
        self.current_owner.plan = PlanName.CODECOV_PRO_YEARLY.value
        self.current_owner.save()
        response = self._retrieve()
        assert response.status_code == status.HTTP_200_OK
        assert response.data["plan"] == {
            "marketing_name": "Pro",
            "value": PlanName.CODECOV_PRO_YEARLY.value,
            "billing_rate": "annually",
            "base_unit_price": 10,
            "benefits": [
                "Configurable # of users",
                "Unlimited public repositories",
                "Unlimited private repositories",
                "Priority Support",
            ],
            "quantity": self.current_owner.plan_user_count,
        }

    def test_retrieve_account_returns_401_if_not_authenticated(self):
        owner = OwnerFactory()
        self.client.logout()
        response = self._retrieve(
            kwargs={"service": owner.service, "owner_username": owner.username}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_retrieve_account_returns_401_if_no_current_owner(self):
        owner = OwnerFactory()
        user = UserFactory()
        self.client.logout()
        self.client.force_login(user)
        response = self._retrieve(
            kwargs={"service": owner.service, "owner_username": owner.username}
        )
        assert response.status_code == 403

    def test_retrieve_account_returns_404_if_user_not_member(self):
        owner = OwnerFactory()
        response = self._retrieve(
            kwargs={"service": owner.service, "owner_username": owner.username}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("services.billing.stripe.Subscription.retrieve")
    def test_retrieve_subscription_with_stripe_invoice_data(self, mock_subscription):
        f = open("./services/tests/samples/stripe_invoice.json")

        default_payment_method = {
            "card": {
                "brand": "visa",
                "exp_month": 12,
                "exp_year": 2024,
                "last4": "abcd",
                "should be": "removed",
            }
        }

        subscription_params = {
            "default_payment_method": default_payment_method,
            "cancel_at_period_end": False,
            "current_period_end": 1633512445,
            "latest_invoice": json.load(f)["data"][0],
            "schedule_id": None,
            "collection_method": "charge_automatically",
            "tax_ids": None,
        }

        mock_subscription.return_value = MockSubscription(subscription_params)

        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.save()

        response = self._retrieve()

        assert response.status_code == status.HTTP_200_OK
        assert response.data["subscription_detail"] == {
            "cancel_at_period_end": False,
            "current_period_end": 1633512445,
            "latest_invoice": self.expected_invoice,
            "default_payment_method": {
                "card": {
                    "brand": "visa",
                    "exp_month": 12,
                    "exp_year": 2024,
                    "last4": "abcd",
                }
            },
            "customer": {"id": "cus_LK&*Hli8YLIO", "discount": None, "email": None},
            "collection_method": "charge_automatically",
            "trial_end": None,
            "tax_ids": None,
        }

    @patch("services.billing.stripe.Subscription.retrieve")
    def test_retrieve_handles_stripe_error(self, mock_get_subscription):
        code, message = 404, "Didn't find that"
        mock_get_subscription.side_effect = StripeError(
            message=message, http_status=code
        )
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.save()

        response = self._retrieve()

        assert response.status_code == code
        assert response.data["detail"] == message

    def test_update_can_set_plan_auto_activate_to_true(self):
        self.current_owner.plan_auto_activate = False
        self.current_owner.save()

        response = self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"plan_auto_activate": True},
        )

        assert response.status_code == status.HTTP_200_OK

        self.current_owner.refresh_from_db()

        assert self.current_owner.plan_auto_activate is True
        assert response.data["plan_auto_activate"] is True

    def test_update_can_set_plan_auto_activate_to_false(self):
        self.current_owner.plan_auto_activate = True
        self.current_owner.save()

        response = self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"plan_auto_activate": False},
        )

        assert response.status_code == status.HTTP_200_OK

        self.current_owner.refresh_from_db()

        assert self.current_owner.plan_auto_activate is False
        assert response.data["plan_auto_activate"] is False

    def test_update_can_set_plan_auto_activate_on_org_with_account(self):
        self.current_owner.account = AccountFactory()
        self.current_owner.plan_auto_activate = True
        self.current_owner.save()

        response = self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"plan_auto_activate": False},
        )

        assert response.status_code == status.HTTP_200_OK

        self.current_owner.refresh_from_db()

        assert self.current_owner.plan_auto_activate is False
        assert response.data["plan_auto_activate"] is False

    def test_update_can_set_plan_to_users_developer_should_set_to_developer(self):
        self.current_owner.plan = PlanName.CODECOV_PRO_YEARLY.value
        self.current_owner.save()

        response = self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"plan": {"value": DEFAULT_FREE_PLAN}},
        )

        assert response.status_code == status.HTTP_200_OK

        self.current_owner.refresh_from_db()

        assert self.current_owner.plan == DEFAULT_FREE_PLAN
        assert self.current_owner.plan_activated_users is None
        assert self.current_owner.plan_user_count == 1
        assert response.data["plan_auto_activate"] is True

    @patch("services.billing.stripe.checkout.Session.create")
    def test_update_can_upgrade_to_paid_plan_for_new_customer_and_return_checkout_session_id(
        self, create_checkout_session_mock
    ):
        expected_id = "this is the id"
        create_checkout_session_mock.return_value = {"id": expected_id}
        self.current_owner.stripe_subscription_id = None
        self.current_owner.save()

        response = self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"plan": {"quantity": 25, "value": PlanName.CODECOV_PRO_YEARLY.value}},
        )

        create_checkout_session_mock.assert_called_once()

        assert response.status_code == status.HTTP_200_OK
        assert response.data["checkout_session_id"] == expected_id

    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.Subscription.modify")
    def test_update_can_upgrade_to_paid_plan_for_existing_customer_and_set_plan_info(
        self, modify_subscription_mock, retrieve_subscription_mock
    ):
        desired_plan = {"value": PlanName.CODECOV_PRO_MONTHLY.value, "quantity": 12}
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.plan = PlanName.CODECOV_PRO_MONTHLY.value
        self.current_owner.plan_user_count = 8
        self.current_owner.save()

        f = open("./services/tests/samples/stripe_invoice.json")

        default_payment_method = {
            "card": {
                "brand": "visa",
                "exp_month": 12,
                "exp_year": 2024,
                "last4": "abcd",
                "should be": "removed",
            }
        }

        subscription_params = {
            "default_payment_method": default_payment_method,
            "latest_invoice": json.load(f)["data"][0],
            "schedule_id": None,
            "collection_method": "charge_automatically",
            "tax_ids": None,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)
        modify_subscription_mock.return_value = MockSubscription(subscription_params)

        response = self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"plan": desired_plan},
        )

        modify_subscription_mock.assert_called_once()

        assert response.status_code == status.HTTP_200_OK
        assert response.data["plan"]["value"] == desired_plan["value"]
        assert response.data["plan"]["quantity"] == desired_plan["quantity"]

        self.current_owner.refresh_from_db()
        assert self.current_owner.plan == desired_plan["value"]
        assert self.current_owner.plan_user_count == desired_plan["quantity"]

    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.Subscription.modify")
    def test_upgrade_payment_failure(
        self, modify_subscription_mock, retrieve_subscription_mock
    ):
        desired_plan = {"value": PlanName.CODECOV_PRO_MONTHLY.value, "quantity": 12}
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.plan = PlanName.CODECOV_PRO_MONTHLY.value
        self.current_owner.plan_user_count = 8
        self.current_owner.delinquent = False
        self.current_owner.save()

        f = open("./services/tests/samples/stripe_invoice.json")

        default_payment_method = {
            "card": {
                "brand": "visa",
                "exp_month": 12,
                "exp_year": 2024,
                "last4": "abcd",
                "should be": "removed",
            }
        }
        subscription_params = {
            "default_payment_method": default_payment_method,
            "latest_invoice": json.load(f)["data"][0],
            "schedule_id": None,
            "collection_method": "charge_automatically",
            "tax_ids": None,
            "pending_update": {
                "expires_at": 1571194285,
                "subscription_items": [
                    {
                        "id": "si_09IkI4u3ZypJUk5onGUZpe8O",
                        "price": "price_CBb6IXqvTLXp3f",
                    }
                ],
            },
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)
        modify_subscription_mock.return_value = MockSubscription(subscription_params)

        response = self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"plan": desired_plan},
        )

        modify_subscription_mock.assert_called_once()

        assert response.status_code == status.HTTP_200_OK
        assert response.data["plan"]["value"] == desired_plan["value"]
        assert response.data["plan"]["quantity"] == 8

        self.current_owner.refresh_from_db()
        assert self.current_owner.plan == desired_plan["value"]
        assert self.current_owner.plan_user_count == 8
        assert self.current_owner.delinquent == True

    def test_update_requires_quantity_if_updating_to_paid_plan(self):
        desired_plan = {"value": PlanName.CODECOV_PRO_YEARLY.value}
        response = self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"plan": desired_plan},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_quantity_must_be_greater_or_equal_to_current_activated_users_if_paid_plan(
        self,
    ):
        self.current_owner.plan_activated_users = [1] * 15
        self.current_owner.save()
        desired_plan = {"value": PlanName.CODECOV_PRO_MONTHLY.value, "quantity": 14}

        response = self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"plan": desired_plan},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("services.billing.stripe.checkout.Session.create")
    def test_update_must_validate_active_users_without_counting_active_students(
        self, create_checkout_session_mock
    ):
        expected_id = "sample id"
        create_checkout_session_mock.return_value = {"id": expected_id}
        self.current_owner.stripe_subscription_id = None
        self.current_owner.plan_activated_users = [
            OwnerFactory(student=False).ownerid,
            OwnerFactory(student=False).ownerid,
            OwnerFactory(student=False).ownerid,
            OwnerFactory(student=False).ownerid,
            OwnerFactory(student=False).ownerid,
            OwnerFactory(student=False).ownerid,
            OwnerFactory(student=False).ownerid,
            OwnerFactory(student=True).ownerid,
            OwnerFactory(student=True).ownerid,
            OwnerFactory(student=True).ownerid,
        ]
        self.current_owner.save()
        desired_plan = {"value": PlanName.CODECOV_PRO_YEARLY.value, "quantity": 8}

        response = self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"plan": desired_plan},
        )

        create_checkout_session_mock.assert_called_once()
        assert response.status_code == status.HTTP_200_OK

    def test_update_must_fail_if_quantity_is_lower_than_activated_user_count(self):
        self.current_owner.plan_activated_users = [
            OwnerFactory(student=False).ownerid,
            OwnerFactory(student=False).ownerid,
            OwnerFactory(student=False).ownerid,
            OwnerFactory(student=False).ownerid,
            OwnerFactory(student=False).ownerid,
            OwnerFactory(student=False).ownerid,
            OwnerFactory(student=False).ownerid,
            OwnerFactory(student=False).ownerid,
            OwnerFactory(student=False).ownerid,
            OwnerFactory(student=False).ownerid,
        ]
        self.current_owner.save()
        desired_plan = {"value": PlanName.CODECOV_PRO_YEARLY.value, "quantity": 8}

        response = self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"plan": desired_plan},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            response.data["plan"]["non_field_errors"][0]
            == "Quantity cannot be lower than currently activated user count"
        )

    def test_update_must_fail_if_quantity_and_plan_are_equal_to_the_owners_current_ones(
        self,
    ):
        self.current_owner.plan = PlanName.CODECOV_PRO_YEARLY.value
        self.current_owner.plan_user_count = 14
        self.current_owner.save()
        desired_plan = {"value": PlanName.CODECOV_PRO_YEARLY.value, "quantity": 14}

        response = self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"plan": desired_plan},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            response.data["plan"]["non_field_errors"][0]
            == "Quantity or plan for paid plan must be different from the existing one"
        )

    def test_update_team_plan_must_fail_if_too_many_activated_users_during_trial(self):
        self.current_owner.plan = DEFAULT_FREE_PLAN
        self.current_owner.plan_user_count = 1
        self.current_owner.trial_status = TrialStatus.ONGOING.value
        self.current_owner.plan_activated_users = list(range(11))
        self.current_owner.save()

        desired_plans = [
            {"value": PlanName.TEAM_MONTHLY.value, "quantity": 10},
            {"value": PlanName.TEAM_YEARLY.value, "quantity": 10},
        ]

        for desired_plan in desired_plans:
            response = self._update(
                kwargs={
                    "service": self.current_owner.service,
                    "owner_username": self.current_owner.username,
                },
                data={"plan": desired_plan},
            )

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid value for plan:" in response.json()["plan"]["value"][0]

    def test_update_team_plan_must_fail_if_currently_team_plan_add_too_many_users(self):
        self.current_owner.plan = PlanName.TEAM_MONTHLY.value
        self.current_owner.plan_user_count = 1
        self.current_owner.save()

        desired_plans = [
            {"value": PlanName.TEAM_MONTHLY.value, "quantity": 11},
            {"value": PlanName.TEAM_YEARLY.value, "quantity": 11},
        ]

        for desired_plan in desired_plans:
            response = self._update(
                kwargs={
                    "service": self.current_owner.service,
                    "owner_username": self.current_owner.username,
                },
                data={"plan": desired_plan},
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert (
                response.data["plan"]["non_field_errors"][0]
                == "Quantity for Team plan cannot exceed 10"
            )

    def test_update_must_fail_if_team_plan_and_too_many_users(self):
        desired_plans = [
            {"value": PlanName.TEAM_MONTHLY.value, "quantity": 11},
            {"value": PlanName.TEAM_YEARLY.value, "quantity": 11},
        ]

        for desired_plan in desired_plans:
            response = self._update(
                kwargs={
                    "service": self.current_owner.service,
                    "owner_username": self.current_owner.username,
                },
                data={"plan": desired_plan},
            )

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert (
                response.data["plan"]["non_field_errors"][0]
                == "Quantity for Team plan cannot exceed 10"
            )

    def test_update_quantity_must_fail_if_account(self):
        desired_plans = [
            {"quantity": 10},
        ]
        self.current_owner.account = AccountFactory()
        self.current_owner.save()
        for desired_plan in desired_plans:
            response = self._update(
                kwargs={
                    "service": self.current_owner.service,
                    "owner_username": self.current_owner.username,
                },
                data={"plan": desired_plan},
            )

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert (
                str(response.data["plan"]["non_field_errors"][0])
                == "You cannot update your plan manually, for help or changes to plan, connect with sales@codecov.io"
            )

    def test_update_plan_must_fail_if_account(self):
        desired_plans = [
            {"value": PlanName.CODECOV_PRO_YEARLY.value},
        ]
        self.current_owner.account = AccountFactory()
        self.current_owner.save()
        for desired_plan in desired_plans:
            response = self._update(
                kwargs={
                    "service": self.current_owner.service,
                    "owner_username": self.current_owner.username,
                },
                data={"plan": desired_plan},
            )

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert (
                str(response.data["plan"]["non_field_errors"][0])
                == "You cannot update your plan manually, for help or changes to plan, connect with sales@codecov.io"
            )

    def test_update_quantity_must_be_at_least_2_if_paid_plan(self):
        desired_plan = {"value": PlanName.CODECOV_PRO_YEARLY.value, "quantity": 1}
        response = self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"plan": desired_plan},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            response.data["plan"]["non_field_errors"][0]
            == "Quantity for paid plan must be greater than 1"
        )

    def test_update_payment_method_without_body(self):
        kwargs = {
            "service": self.current_owner.service,
            "owner_username": self.current_owner.username,
        }
        url = reverse("account_details-update-payment", kwargs=kwargs)
        response = self.client.patch(url, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("services.billing.StripeService._is_unverified_payment_method")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.PaymentMethod.attach")
    @patch("services.billing.stripe.Customer.modify")
    @patch("services.billing.stripe.Subscription.modify")
    def test_update_payment_method(
        self,
        modify_subscription_mock,
        modify_customer_mock,
        attach_payment_mock,
        retrieve_subscription_mock,
        is_unverified_payment_method_mock,
    ):
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.save()
        f = open("./services/tests/samples/stripe_invoice.json")

        is_unverified_payment_method_mock.return_value = False

        default_payment_method = {
            "card": {
                "brand": "visa",
                "exp_month": 12,
                "exp_year": 2024,
                "last4": "abcd",
                "should be": "removed",
            }
        }

        subscription_params = {
            "default_payment_method": default_payment_method,
            "cancel_at_period_end": False,
            "current_period_end": 1633512445,
            "latest_invoice": json.load(f)["data"][0],
            "schedule_id": None,
            "collection_method": "charge_automatically",
            "tax_ids": None,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        payment_method_id = "pm_123"
        kwargs = {
            "service": self.current_owner.service,
            "owner_username": self.current_owner.username,
        }
        data = {"payment_method": payment_method_id}
        url = reverse("account_details-update-payment", kwargs=kwargs)
        response = self.client.patch(url, data=data, format="json")
        assert response.status_code == status.HTTP_200_OK
        attach_payment_mock.assert_called_once_with(
            payment_method_id, customer=self.current_owner.stripe_customer_id
        )
        modify_customer_mock.assert_called_once_with(
            self.current_owner.stripe_customer_id,
            invoice_settings={"default_payment_method": payment_method_id},
        )

        modify_subscription_mock.assert_called_once_with(
            self.current_owner.stripe_subscription_id,
            default_payment_method=payment_method_id,
        )

    @patch("services.billing.StripeService.update_payment_method")
    def test_update_payment_method_handles_stripe_error(self, upm_mock):
        code, message = 402, "Oops, nope"
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.save()

        upm_mock.side_effect = StripeError(message=message, http_status=code)

        payment_method_id = "pm_123"
        kwargs = {
            "service": self.current_owner.service,
            "owner_username": self.current_owner.username,
        }
        data = {"payment_method": payment_method_id}
        url = reverse("account_details-update-payment", kwargs=kwargs)
        response = self.client.patch(url, data=data, format="json")
        assert response.status_code == code
        assert response.data["detail"] == message

    def test_update_email_address_without_body(self):
        kwargs = {
            "service": self.current_owner.service,
            "owner_username": self.current_owner.username,
        }
        url = reverse("account_details-update-email", kwargs=kwargs)
        response = self.client.patch(url, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("services.billing.StripeService.update_email_address")
    def test_update_email_address_handles_stripe_error(self, stripe_mock):
        code, message = 402, "Oops, nope"
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.save()

        stripe_mock.side_effect = StripeError(message=message, http_status=code)

        new_email = "test@gmail.com"
        kwargs = {
            "service": self.current_owner.service,
            "owner_username": self.current_owner.username,
        }
        data = {"new_email": new_email}
        url = reverse("account_details-update-email", kwargs=kwargs)
        response = self.client.patch(url, data=data, format="json")
        assert response.status_code == code
        assert response.data["detail"] == message

    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.Customer.modify")
    def test_update_email_address(self, modify_customer_mock, retrieve_mock):
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.save()

        new_email = "test@gmail.com"
        kwargs = {
            "service": self.current_owner.service,
            "owner_username": self.current_owner.username,
        }
        data = {"new_email": new_email}
        url = reverse("account_details-update-email", kwargs=kwargs)
        response = self.client.patch(url, data=data, format="json")
        assert response.status_code == status.HTTP_200_OK

        modify_customer_mock.assert_called_once_with(
            self.current_owner.stripe_customer_id, email=new_email
        )

    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.Customer.modify")
    @patch("services.billing.stripe.PaymentMethod.modify")
    @patch("services.billing.stripe.Customer.retrieve")
    def test_update_email_address_with_propagate(
        self,
        customer_retrieve_mock,
        payment_method_mock,
        modify_customer_mock,
        retrieve_mock,
    ):
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.save()

        payment_method_id = "pm_123"
        customer_retrieve_mock.return_value = {
            "invoice_settings": {"default_payment_method": payment_method_id}
        }

        new_email = "test@gmail.com"
        kwargs = {
            "service": self.current_owner.service,
            "owner_username": self.current_owner.username,
        }
        data = {"new_email": new_email, "apply_to_default_payment_method": True}
        url = reverse("account_details-update-email", kwargs=kwargs)
        response = self.client.patch(url, data=data, format="json")
        assert response.status_code == status.HTTP_200_OK

        modify_customer_mock.assert_called_once_with(
            self.current_owner.stripe_customer_id, email=new_email
        )
        customer_retrieve_mock.assert_called_once_with(
            self.current_owner.stripe_customer_id
        )
        payment_method_mock.assert_called_once_with(
            payment_method_id, billing_details={"email": new_email}
        )

    def test_update_billing_address_without_body(self):
        kwargs = {
            "service": self.current_owner.service,
            "owner_username": self.current_owner.username,
        }
        url = reverse("account_details-update-billing-address", kwargs=kwargs)
        response = self.client.patch(url, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_billing_address_without_name(self):
        kwargs = {
            "service": self.current_owner.service,
            "owner_username": self.current_owner.username,
        }
        billing_address = {
            "line_1": "45 Fremont St.",
            "line_2": "",
            "city": "San Francisco",
            "state": "CA",
            "country": "US",
            "postal_code": "94105",
        }
        data = {"billing_address": billing_address}
        url = reverse("account_details-update-billing-address", kwargs=kwargs)
        response = self.client.patch(url, data=data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_update_billing_address_without_address(self):
        kwargs = {
            "service": self.current_owner.service,
            "owner_username": self.current_owner.username,
        }
        data = {"name": "John Doe"}
        url = reverse("account_details-update-billing-address", kwargs=kwargs)
        response = self.client.patch(url, data=data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch("services.billing.StripeService.update_billing_address")
    def test_update_billing_address_handles_stripe_error(self, stripe_mock):
        code, message = 402, "Oops, nope"
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.save()

        stripe_mock.side_effect = StripeError(message=message, http_status=code)

        billing_address = {
            "line_1": "45 Fremont St.",
            "line_2": "",
            "city": "San Francisco",
            "state": "CA",
            "country": "US",
            "postal_code": "94105",
        }
        kwargs = {
            "service": self.current_owner.service,
            "owner_username": self.current_owner.username,
        }
        data = {"name": "John Doe", "billing_address": billing_address}
        url = reverse("account_details-update-billing-address", kwargs=kwargs)
        response = self.client.patch(url, data=data, format="json")
        assert response.status_code == code
        assert response.data["detail"] == message

    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.Customer.retrieve")
    @patch("services.billing.stripe.PaymentMethod.modify")
    @patch("services.billing.stripe.Customer.modify")
    def test_update_billing_address(
        self,
        modify_customer_mock,
        modify_payment_mock,
        retrieve_customer_mock,
        retrieve_sub_mock,
    ):
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.save()
        f = open("./services/tests/samples/stripe_invoice.json")

        billing_address = {
            "line_1": "45 Fremont St.",
            "line_2": "",
            "city": "San Francisco",
            "state": "CA",
            "country": "US",
            "postal_code": "94105",
        }

        formatted_address = {
            "line1": "45 Fremont St.",
            "line2": "",
            "city": "San Francisco",
            "state": "CA",
            "country": "US",
            "postal_code": "94105",
        }

        default_payment_method = {
            "id": "pm_123",
            "card": {
                "brand": "visa",
                "exp_month": 12,
                "exp_year": 2024,
                "last4": "abcd",
            },
        }

        subscription_params = {
            "default_payment_method": default_payment_method,
            "cancel_at_period_end": False,
            "current_period_end": 1633512445,
            "latest_invoice": json.load(f)["data"][0],
            "schedule_id": None,
            "collection_method": "charge_automatically",
            "tax_ids": None,
        }

        retrieve_sub_mock.return_value = MockSubscription(subscription_params)

        kwargs = {
            "service": self.current_owner.service,
            "owner_username": self.current_owner.username,
        }
        data = {"name": "John Doe", "billing_address": billing_address}
        url = reverse("account_details-update-billing-address", kwargs=kwargs)
        response = self.client.patch(url, data=data, format="json")
        assert response.status_code == status.HTTP_200_OK

        retrieve_customer_mock.assert_called_once()
        modify_payment_mock.assert_called_once()
        modify_customer_mock.assert_called_once_with(
            self.current_owner.stripe_customer_id, address=formatted_address
        )

    @patch("api.shared.permissions.get_provider")
    def test_update_without_admin_permissions_returns_404(self, get_provider_mock):
        get_provider_mock.return_value = GetAdminProviderAdapter()
        owner = OwnerFactory()
        response = self._update(
            kwargs={"service": owner.service, "owner_username": owner.username}, data={}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_update_can_change_name_and_email(self):
        expected_name, expected_email = "Scooby Doo", "scoob@snack.com"
        response = self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"name": expected_name, "email": expected_email},
        )

        assert response.data["name"] == expected_name
        assert response.data["email"] == expected_email
        self.current_owner.refresh_from_db()
        assert self.current_owner.name == expected_name
        assert self.current_owner.email == expected_email

    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.StripeService.modify_subscription")
    def test_update_handles_stripe_error(self, retrieve_sub_mock, modify_sub_mock):
        code, message = 402, "Not right, wrong in fact"
        desired_plan = {"value": PlanName.CODECOV_PRO_MONTHLY.value, "quantity": 12}
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.save()
        retrieve_sub_mock.return_value = MockSubscription({})
        modify_sub_mock.side_effect = StripeError(message=message, http_status=code)

        response = self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"plan": desired_plan},
        )

        assert response.status_code == code
        assert response.data["detail"] == message

    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("api.internal.owner.serializers.send_sentry_webhook")
    @patch("services.billing.StripeService.modify_subscription")
    def test_update_sentry_plan_monthly(
        self, modify_sub_mock, send_sentry_webhook, retrieve_sub_mock
    ):
        desired_plan = {"value": PlanName.SENTRY_MONTHLY.value, "quantity": 12}
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.sentry_user_id = "sentry-user-id"
        self.current_owner.save()

        self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"plan": desired_plan},
        )
        send_sentry_webhook.assert_called_once_with(
            self.current_owner, self.current_owner
        )

    @patch("api.internal.owner.serializers.send_sentry_webhook")
    @patch("services.billing.StripeService.modify_subscription")
    def test_update_sentry_plan_monthly_with_users_org(
        self, modify_sub_mock, send_sentry_webhook
    ):
        desired_plan = {"value": PlanName.SENTRY_MONTHLY.value, "quantity": 12}
        org = OwnerFactory(
            service=Service.GITHUB.value,
            service_id="923836740",
        )

        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.sentry_user_id = "sentry-user-id"
        self.current_owner.organizations = [org.ownerid]
        self.current_owner.save()

        self._update(
            kwargs={"service": org.service, "owner_username": org.username},
            data={"plan": desired_plan},
        )
        send_sentry_webhook.assert_called_once_with(self.current_owner, org)

    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("api.internal.owner.serializers.send_sentry_webhook")
    @patch("services.billing.StripeService.modify_subscription")
    def test_update_sentry_plan_annual(
        self,
        modify_sub_mock,
        send_sentry_webhook,
        retrieve_sub_mock,
    ):
        desired_plan = {"value": PlanName.SENTRY_YEARLY.value, "quantity": 12}
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.sentry_user_id = "sentry-user-id"
        self.current_owner.save()

        self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"plan": desired_plan},
        )
        send_sentry_webhook.assert_called_once_with(
            self.current_owner, self.current_owner
        )

    @patch("api.internal.owner.serializers.send_sentry_webhook")
    @patch("services.billing.StripeService.modify_subscription")
    def test_update_sentry_plan_annual_with_users_org(
        self, modify_sub_mock, send_sentry_webhook
    ):
        desired_plan = {"value": PlanName.SENTRY_YEARLY.value, "quantity": 12}
        org = OwnerFactory(
            service=Service.GITHUB.value,
            service_id="923836740",
        )
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.sentry_user_id = "sentry-user-id"
        self.current_owner.organizations = [org.ownerid]
        self.current_owner.save()

        self._update(
            kwargs={"service": org.service, "owner_username": org.username},
            data={"plan": desired_plan},
        )
        send_sentry_webhook.assert_called_once_with(self.current_owner, org)

    @patch("api.internal.owner.serializers.send_sentry_webhook")
    @patch("services.billing.StripeService.modify_subscription")
    def test_update_sentry_plan_non_sentry_user(
        self, modify_sub_mock, send_sentry_webhook
    ):
        desired_plan = {"value": PlanName.SENTRY_MONTHLY.value, "quantity": 5}
        org = OwnerFactory(
            service=Service.GITHUB.value,
            service_id="923836740",
        )
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.sentry_user_id = None
        self.current_owner.organizations = [org.ownerid]
        self.current_owner.save()

        res = self._update(
            kwargs={"service": org.service, "owner_username": org.username},
            data={"plan": desired_plan},
        )

        # cannot upgrade to Sentry plan
        assert res.status_code == 400
        assert res.json() == {
            "plan": {
                "value": [
                    f"Invalid value for plan: users-sentrym; must be one of ['users-pr-inappm', 'users-pr-inappy', 'users-teamm', 'users-teamy', '{DEFAULT_FREE_PLAN}']"
                ]
            }
        }

    @patch("services.billing.stripe.Coupon.create")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.Customer.modify")
    def test_update_apply_cancellation_discount(
        self, modify_customer_mock, retrieve_subscription_mock, coupon_create_mock
    ):
        coupon_create_mock.return_value = MagicMock(id="test-coupon-id")

        self.current_owner.plan = PlanName.CODECOV_PRO_MONTHLY.value
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.save()

        subscription_params = {
            "default_payment_method": None,
            "cancel_at_period_end": False,
            "current_period_end": 1633512445,
            "latest_invoice": None,
            "schedule_id": None,
            "collection_method": "charge_automatically",
            "customer_coupon": {
                "name": "30% off for 6 months",
                "percent_off": 30.0,
                "duration_in_months": 6,
                "created": int(datetime(2023, 1, 1, 0, 0, 0).timestamp()),
            },
            "tax_ids": None,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        response = self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"apply_cancellation_discount": True},
        )

        modify_customer_mock.assert_called_once_with(
            self.current_owner.stripe_customer_id,
            coupon="test-coupon-id",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["subscription_detail"]["customer"]["discount"] == {
            "name": "30% off for 6 months",
            "percent_off": 30.0,
            "duration_in_months": 6,
            "expires": int(datetime(2023, 7, 1, 0, 0, 0).timestamp()),
        }

    @patch("services.billing.stripe.Coupon.create")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.Customer.modify")
    def test_update_apply_cancellation_discount_yearly(
        self, modify_customer_mock, retrieve_subscription_mock, coupon_create_mock
    ):
        coupon_create_mock.return_value = MagicMock(id="test-coupon-id")

        self.current_owner.plan = PlanName.CODECOV_PRO_YEARLY.value
        self.current_owner.stripe_customer_id = "flsoe"
        self.current_owner.stripe_subscription_id = "djfos"
        self.current_owner.save()

        subscription_params = {
            "default_payment_method": None,
            "cancel_at_period_end": False,
            "current_period_end": 1633512445,
            "latest_invoice": None,
            "schedule_id": None,
            "collection_method": "charge_automatically",
            "tax_ids": None,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        response = self._update(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            },
            data={"apply_cancellation_discount": True},
        )

        assert not modify_customer_mock.called
        assert not coupon_create_mock.called
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["subscription_detail"]["customer"]["discount"] is None

    @patch("services.task.TaskService.delete_owner")
    def test_destroy_triggers_delete_owner_task(self, delete_owner_mock):
        response = self._destroy(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            }
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        delete_owner_mock.assert_called_once_with(self.current_owner.ownerid)

    def test_destroy_not_own_account_returns_404(self):
        owner = OwnerFactory(admins=[self.current_owner.ownerid])
        response = self._destroy(
            kwargs={"service": owner.service, "owner_username": owner.username}
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_org_with_account(self):
        account = AccountFactory(
            name="Hello World",
            plan_seat_count=5,
            free_seat_count=3,
            plan=PlanName.ENTERPRISE_CLOUD_YEARLY.value,
            is_delinquent=False,
        )
        InvoiceBillingFactory(is_active=True, account=account)
        org_1 = OwnerFactory(
            account=account,
            service=Service.GITHUB.value,
            username="Test",
            delinquent=True,
            uses_invoice=False,
        )
        org_2 = OwnerFactory(
            account=account,
            service=Service.GITHUB.value,
        )
        activated_owner = OwnerFactory(
            user=UserFactory(), organizations=[org_1.ownerid, org_2.ownerid]
        )
        account.users.add(activated_owner.user)
        student_owner = OwnerFactory(
            user=UserFactory(),
            student=True,
            organizations=[org_1.ownerid, org_2.ownerid],
        )
        account.users.add(student_owner.user)
        other_activated_owner = OwnerFactory(
            user=UserFactory(), organizations=[org_2.ownerid]
        )
        account.users.add(other_activated_owner.user)
        other_student_owner = OwnerFactory(
            user=UserFactory(),
            student=True,
            organizations=[org_2.ownerid],
        )
        account.users.add(other_student_owner.user)
        org_1.plan_activated_users = [activated_owner.ownerid, student_owner.ownerid]
        org_1.admins = [activated_owner.ownerid]
        org_1.save()
        org_2.plan_activated_users = [
            activated_owner.ownerid,
            student_owner.ownerid,
            other_activated_owner.ownerid,
            other_student_owner.ownerid,
        ]
        org_2.save()

        self.client.force_login_owner(activated_owner)
        response = self._retrieve(
            kwargs={"service": Service.GITHUB.value, "owner_username": org_1.username}
        )
        assert response.status_code == status.HTTP_200_OK
        # these fields are all overridden by account fields if the org has an account
        self.assertEqual(org_1.activated_user_count, 1)
        self.assertEqual(org_1.activated_student_count, 1)
        self.assertTrue(org_1.delinquent)
        self.assertFalse(org_1.uses_invoice)
        self.assertEqual(org_1.plan_user_count, 1)
        expected_response = {
            "activated_user_count": 2,
            "activated_student_count": 2,
            "delinquent": False,
            "uses_invoice": True,
            "plan": {
                "marketing_name": "Enterprise Cloud",
                "value": PlanName.ENTERPRISE_CLOUD_YEARLY.value,
                "billing_rate": "annually",
                "base_unit_price": 10,
                "benefits": [
                    "Configurable # of users",
                    "Unlimited public repositories",
                    "Unlimited private repositories",
                    "Priority Support",
                ],
                "quantity": 5,
            },
            "root_organization": None,
            "integration_id": org_1.integration_id,
            "plan_auto_activate": org_1.plan_auto_activate,
            "inactive_user_count": 0,
            "subscription_detail": None,
            "checkout_session_id": None,
            "name": org_1.name,
            "email": org_1.email,
            "nb_active_private_repos": 0,
            "repo_total_credits": 99999999,
            "plan_provider": org_1.plan_provider,
            "student_count": 1,
            "schedule_detail": None,
        }
        self.assertDictEqual(response.data["plan"], expected_response["plan"])
        self.assertDictEqual(response.data, expected_response)


@override_settings(IS_ENTERPRISE=True)
class EnterpriseAccountViewSetTests(APITestCase):
    def _retrieve(self, kwargs={}):
        if not kwargs:
            kwargs = {
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            }
        return self.client.get(reverse("account_details-detail", kwargs=kwargs))

    def _update(self, kwargs, data):
        return self.client.patch(
            reverse("account_details-detail", kwargs=kwargs), data=data, format="json"
        )

    def _destroy(self, kwargs):
        return self.client.delete(reverse("account_details-detail", kwargs=kwargs))

    def setUp(self):
        self.service = "gitlab"
        self.current_owner = OwnerFactory(
            stripe_customer_id=1000,
            service=Service.GITHUB.value,
            service_id="10238974029348",
        )
        self.client = APIClient()
        self.client.force_login_owner(self.current_owner)

    def test_retrieve_own_account_give_200(self):
        response = self._retrieve(
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
            }
        )
        assert response.status_code == status.HTTP_200_OK
