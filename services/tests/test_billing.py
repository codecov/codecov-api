import json
from unittest.mock import MagicMock, call, patch

import requests
import stripe
from django.conf import settings
from django.test import TestCase
from freezegun import freeze_time
from shared.django_apps.core.tests.factories import OwnerFactory
from shared.plan.constants import DEFAULT_FREE_PLAN, PlanName
from stripe import InvalidRequestError
from stripe.api_resources import PaymentIntent, SetupIntent

from billing.helpers import mock_all_plans_and_tiers
from codecov_auth.models import Plan, Service
from services.billing import AbstractPaymentService, BillingService, StripeService

SCHEDULE_RELEASE_OFFSET = 10

expected_invoices = [
    {
        "id": "in_19yTU92eZvKYlo2C7uDjvu6v",
        "object": "invoice",
        "account_country": "US",
        "account_name": "Stripe.com",
        "amount_due": 999,
        "amount_paid": 999,
        "amount_remaining": 0,
        "application_fee_amount": None,
        "attempt_count": 1,
        "attempted": True,
        "auto_advance": False,
        "billing_reason": None,
        "charge": "ch_19yUQN2eZvKYlo2CQf7aWpSX",
        "collection_method": "charge_automatically",
        "created": 1489789429,
        "currency": "usd",
        "custom_fields": None,
        "customer": "cus_HF6p8Zx7JdRS7A",
        "customer_address": "6639 Boulevard Dr, Westwood FL 34202 USA",
        "customer_email": "olivia.williams.03@example.com",
        "customer_name": "Peer Company",
        "customer_phone": None,
        "customer_shipping": None,
        "customer_tax_exempt": "none",
        "customer_tax_ids": [],
        "default_payment_method": None,
        "default_source": None,
        "default_tax_rates": [],
        "description": None,
        "discount": None,
        "due_date": None,
        "ending_balance": 0,
        "footer": None,
        "hosted_invoice_url": "https://pay.stripe.com/invoice/acct_1032D82eZvKYlo2C/invst_a7KV10HpLw2QxrihgVyuOkOjMZ",
        "invoice_pdf": "https://pay.stripe.com/invoice/acct_1032D82eZvKYlo2C/invst_a7KV10HpLw2QxrihgVyuOkOjMZ/pdf",
        "lines": {
            "data": [
                {
                    "id": "il_tmp_06bab3ae5b3624",
                    "object": "line_item",
                    "amount": 120,
                    "currency": "usd",
                    "description": "(10) users-pr-inappm",
                    "discountable": True,
                    "livemode": False,
                    "metadata": {},
                    "period": {"end": 1521326190, "start": 1518906990},
                    "plan": {
                        "id": "ivory-freelance-040",
                        "name": "users-pr-inappm",
                        "object": "plan",
                        "active": True,
                        "aggregate_usage": None,
                        "amount": 999,
                        "amount_decimal": "999",
                        "billing_scheme": "per_unit",
                        "created": 1466202980,
                        "currency": "usd",
                        "interval": "month",
                        "interval_count": 1,
                        "livemode": False,
                        "metadata": {},
                        "nickname": None,
                        "product": "prod_BUthVRQ7KdFfa7",
                        "tiers": None,
                        "tiers_mode": None,
                        "transform_usage": None,
                        "trial_period_days": None,
                        "usage_type": "licensed",
                    },
                    "proration": False,
                    "quantity": 1,
                    "subscription": "sub_8epEF0PuRhmltU",
                    "subscription_item": "si_18NVZi2eZvKYlo2CUtBNGL9x",
                    "tax_amounts": [],
                    "tax_rates": [],
                    "type": "subscription",
                }
            ],
            "has_more": False,
            "object": "list",
            "url": "/v1/invoices/in_19yTU92eZvKYlo2C7uDjvu6v/lines",
        },
        "livemode": False,
        "metadata": {"order_id": "6735"},
        "next_payment_attempt": None,
        "number": "EF0A41E-0001",
        "paid": True,
        "payment_intent": {"id": "pi_3P4567890123456789012345", "status": "completed"},
        "period_end": 1489789420,
        "period_start": 1487370220,
        "post_payment_credit_notes_amount": 0,
        "pre_payment_credit_notes_amount": 0,
        "receipt_number": "2277-9887",
        "starting_balance": 0,
        "statement_descriptor": None,
        "status": "paid",
        "status_transitions": {
            "finalized_at": 1489793039,
            "marked_uncollectible_at": None,
            "paid_at": 1489793039,
            "voided_at": None,
        },
        "subscription": "sub_9lNL2lSXI8nYEQ",
        "subtotal": 999,
        "tax": None,
        "tax_percent": None,
        "total": 999,
        "total_tax_amounts": [],
        "webhooks_delivered_at": 1489789437,
    }
]


class MockSubscriptionPlan(object):
    def __init__(self, params):
        self.id = params["new_plan"]
        self.interval = "year"


class MockSubscription(object):
    def __init__(self, subscription_params):
        self.schedule = subscription_params["schedule_id"]
        self.current_period_start = subscription_params["start_date"]
        self.current_period_end = subscription_params["end_date"]
        self.plan = (
            MockSubscriptionPlan(subscription_params["plan"])
            if subscription_params.get("plan") is not None
            else None
        )
        self.items = {
            "data": [
                {
                    "quantity": subscription_params["quantity"],
                    "id": subscription_params["id"],
                    "plan": {
                        "id": subscription_params["name"],
                        "interval": subscription_params.get("plan", {}).get(
                            "interval", "month"
                        ),
                    },
                }
            ]
        }

    def __getitem__(self, key):
        return getattr(self, key)


class MockFailedSubscriptionUpgrade(object):
    def __init__(self, subscription_params):
        self.id = subscription_params["id"]
        self.object = subscription_params["object"]
        self.pending_update = subscription_params["pending_update"]

    def __getitem__(self, key):
        return getattr(self, key)


class StripeServiceTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_all_plans_and_tiers()

    def setUp(self):
        self.user = OwnerFactory()
        self.stripe = StripeService(requesting_user=self.user)

    def test_stripe_service_requires_requesting_user_to_be_owner_instance(self):
        with self.assertRaises(Exception):
            StripeService(None)

    def _assert_subscription_modify(
        self, subscription_modify_mock, owner, subscription_params, desired_plan
    ):
        plan = Plan.objects.get(name=desired_plan["value"])
        subscription_modify_mock.assert_called_once_with(
            owner.stripe_subscription_id,
            cancel_at_period_end=False,
            items=[
                {
                    "id": subscription_params["id"],
                    "plan": plan.stripe_id,
                    "quantity": desired_plan["quantity"],
                }
            ],
            metadata={
                "service": owner.service,
                "obo_organization": owner.ownerid,
                "username": owner.username,
                "obo_name": self.user.name,
                "obo_email": self.user.email,
                "obo": self.user.ownerid,
            },
            proration_behavior="always_invoice",
            # payment_behavior="pending_if_incomplete",
        )

    def _assert_schedule_modify(
        self,
        schedule_modify_mock,
        owner,
        subscription_params,
        desired_plan,
        schedule_id,
    ):
        plan = Plan.objects.get(name=desired_plan["value"])
        schedule_modify_mock.assert_called_once_with(
            schedule_id,
            end_behavior="release",
            phases=[
                {
                    "start_date": subscription_params["start_date"],
                    "end_date": subscription_params["end_date"],
                    "items": [
                        {
                            "plan": subscription_params["name"],
                            "price": subscription_params["name"],
                            "quantity": subscription_params["quantity"],
                        }
                    ],
                    "proration_behavior": "none",
                },
                {
                    "start_date": subscription_params["end_date"],
                    "end_date": subscription_params["end_date"]
                    + SCHEDULE_RELEASE_OFFSET,
                    "items": [
                        {
                            "plan": plan.stripe_id,
                            "price": plan.stripe_id,
                            "quantity": desired_plan["quantity"],
                        }
                    ],
                    "proration_behavior": "none",
                },
            ],
            metadata={
                "service": owner.service,
                "obo_organization": owner.ownerid,
                "username": owner.username,
                "obo_name": self.user.name,
                "obo_email": self.user.email,
                "obo": self.user.ownerid,
            },
        )

    @patch("services.billing.stripe.Invoice.list")
    def test_list_filtered_invoices_calls_stripe_invoice_list_with_customer_stripe_id(
        self, invoice_list_mock
    ):
        owner = OwnerFactory(stripe_customer_id=-1)
        self.stripe.list_filtered_invoices(owner)
        invoice_list_mock.assert_called_once_with(
            customer=owner.stripe_customer_id, limit=10
        )

    @patch("services.billing.stripe.Invoice.list")
    def test_list_filtered_invoices_returns_expected_invoices(self, invoice_list_mock):
        with open("./services/tests/samples/stripe_invoice.json") as f:
            stripe_invoice_response = json.load(f)
        invoice_list_mock.return_value = stripe_invoice_response
        owner = OwnerFactory(stripe_customer_id=-1)
        invoices = self.stripe.list_filtered_invoices(owner)
        assert invoices == expected_invoices
        assert len(invoices) == 1

    @patch("stripe.Invoice.list")
    def test_list_filtered_invoices_returns_emptylist_if_stripe_customer_id_is_None(
        self, invoice_list_mock
    ):
        owner = OwnerFactory()
        invoices = self.stripe.list_filtered_invoices(owner)

        invoice_list_mock.assert_not_called()
        assert invoices == []

    @patch("services.billing.stripe.Customer.retrieve")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.Subscription.modify")
    def test_delete_subscription_without_schedule_modifies_subscription_to_delete_at_end_of_billing_cycle_if_valid_plan(
        self, modify_mock, retrieve_subscription_mock, retrieve_customer_mock
    ):
        plan = PlanName.CODECOV_PRO_YEARLY.value
        stripe_subscription_id = "sub_1K77Y5GlVGuVgOrkJrLjRnne"
        stripe_schedule_id = None
        customer_id = "cus_HF6p8Zx7JdRS7A"
        owner = OwnerFactory(
            stripe_subscription_id=stripe_subscription_id,
            plan=plan,
            plan_activated_users=[4, 6, 3],
            plan_user_count=9,
            stripe_customer_id=customer_id,
        )
        subscription_params = {
            "schedule_id": stripe_schedule_id,
            "start_date": 1489799420,
            "end_date": 1492477820,
            "quantity": 10,
            "name": plan,
            "id": 215,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)
        retrieve_customer_mock.return_value = {
            "id": "cus_123456789",
            "email": "test@example.com",
            "name": "Test User",
            "metadata": {},
        }
        self.stripe.delete_subscription(owner)
        modify_mock.assert_called_once_with(
            stripe_subscription_id,
            cancel_at_period_end=True,
            proration_behavior="none",
        )
        owner.refresh_from_db()
        assert owner.stripe_subscription_id == stripe_subscription_id
        assert owner.plan == plan
        assert owner.plan_activated_users == [4, 6, 3]
        assert owner.plan_user_count == 9

    @freeze_time("2017-03-22T00:00:00")
    @patch("services.billing.stripe.Customer.retrieve")
    @patch("services.billing.stripe.Refund.create")
    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.SubscriptionSchedule.release")
    def test_delete_subscription_with_schedule_releases_schedule_and_cancels_subscription_at_end_of_billing_cycle_if_valid_plan(
        self,
        schedule_release_mock,
        retrieve_subscription_mock,
        modify_mock,
        create_refund_mock,
        retrieve_customer_mock,
    ):
        plan = PlanName.CODECOV_PRO_YEARLY.value
        stripe_subscription_id = "sub_1K77Y5GlVGuVgOrkJrLjRnne"
        stripe_schedule_id = "sub_sched_sch1K77Y5GlVGuVgOrkJrLjRnne"
        # customer_id = "cus_HF6p8Zx7JdRS7A"
        owner = OwnerFactory(
            stripe_subscription_id=stripe_subscription_id,
            plan=plan,
            plan_activated_users=[4, 6, 3],
            plan_user_count=9,
            # stripe_customer_id=customer_id
        )
        subscription_params = {
            "schedule_id": stripe_schedule_id,
            "start_date": 1489799420,
            "end_date": 1492477820,
            "quantity": 10,
            "name": plan,
            "id": 215,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)
        retrieve_customer_mock.return_value = {
            "id": "cus_123456789",
            "email": "test@example.com",
            "name": "Test User",
            "metadata": {},
        }
        self.stripe.delete_subscription(owner)
        schedule_release_mock.assert_called_once_with(stripe_schedule_id)
        modify_mock.assert_called_once_with(
            stripe_subscription_id,
            cancel_at_period_end=True,
            proration_behavior="none",
        )
        create_refund_mock.assert_not_called()
        owner.refresh_from_db()
        assert owner.stripe_subscription_id == stripe_subscription_id
        assert owner.plan == plan
        assert owner.plan_activated_users == [4, 6, 3]
        assert owner.plan_user_count == 9

    @freeze_time("2017-03-18T00:00:00")
    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.Customer.modify")
    @patch("services.billing.stripe.Refund.create")
    @patch("services.billing.stripe.Invoice.list")
    @patch("services.billing.stripe.Subscription.cancel")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.SubscriptionSchedule.release")
    @patch("services.billing.stripe.Customer.retrieve")
    def test_delete_subscription_with_schedule_releases_schedule_and_cancels_subscription_with_grace_month_refund_if_valid_plan(
        self,
        retrieve_customer_mock,
        schedule_release_mock,
        retrieve_subscription_mock,
        cancel_sub_mock,
        list_invoice_mock,
        create_refund_mock,
        modify_customer_mock,
        modify_sub_mock,
    ):
        with open("./services/tests/samples/stripe_invoice.json") as f:
            stripe_invoice_response = json.load(f)
        list_invoice_mock.return_value = stripe_invoice_response
        plan = PlanName.CODECOV_PRO_YEARLY.value
        stripe_subscription_id = "sub_1K77Y5GlVGuVgOrkJrLjRnne"
        stripe_schedule_id = "sub_sched_sch1K77Y5GlVGuVgOrkJrLjRnne"
        customer_id = "cus_HF6p8Zx7JdRS7A"
        owner = OwnerFactory(
            stripe_subscription_id=stripe_subscription_id,
            plan=plan,
            plan_activated_users=[4, 6, 3],
            plan_user_count=9,
            stripe_customer_id=customer_id,
        )
        subscription_params = {
            "schedule_id": stripe_schedule_id,
            "start_date": 1489799420,
            "end_date": 1492477820,
            "quantity": 10,
            "name": plan,
            "id": 215,
            "plan": {
                "new_plan": "plan_pro_yearly",
                "new_quantity": 7,
                "subscription_id": "sub_123",
                "interval": "month",
            },
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)
        retrieve_customer_mock.return_value = {
            "id": "cus_HF6p8Zx7JdRS7A",
            "metadata": {},
        }
        self.stripe.delete_subscription(owner)
        schedule_release_mock.assert_called_once_with(stripe_schedule_id)
        retrieve_customer_mock.assert_called_once_with(owner.stripe_customer_id)
        cancel_sub_mock.assert_called_once_with(stripe_subscription_id)
        list_invoice_mock.assert_called_once_with(
            subscription=stripe_subscription_id,
            status="paid",
            created={"gte": 1458263420, "lt": 1489799420},
        )
        self.assertEqual(create_refund_mock.call_count, 2)
        modify_customer_mock.assert_called_once_with(
            owner.stripe_customer_id, balance=0, metadata={"autorefunds_remaining": "1"}
        )
        modify_sub_mock.assert_not_called()

        owner.refresh_from_db()
        assert owner.stripe_subscription_id == stripe_subscription_id
        assert owner.plan == plan
        assert owner.plan_activated_users == [4, 6, 3]
        assert owner.plan_user_count == 9

    @freeze_time("2017-03-19T00:00:00")
    @patch("services.billing.stripe.Customer.retrieve")
    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.Customer.modify")
    @patch("services.billing.stripe.Refund.create")
    @patch("services.billing.stripe.Invoice.list")
    @patch("services.billing.stripe.Subscription.cancel")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.SubscriptionSchedule.release")
    def test_delete_subscription_with_schedule_releases_schedule_and_cancels_subscription_with_grace_year_refund_if_valid_plan(
        self,
        schedule_release_mock,
        retrieve_subscription_mock,
        cancel_sub_mock,
        list_invoice_mock,
        create_refund_mock,
        modify_customer_mock,
        modify_sub_mock,
        retrieve_customer_mock,
    ):
        with open("./services/tests/samples/stripe_invoice.json") as f:
            stripe_invoice_response = json.load(f)
        list_invoice_mock.return_value = stripe_invoice_response
        plan = PlanName.CODECOV_PRO_YEARLY.value
        stripe_subscription_id = "sub_1K77Y5GlVGuVgOrkJrLjRnne"
        stripe_schedule_id = "sub_sched_sch1K77Y5GlVGuVgOrkJrLjRnne"
        customer_id = "cus_HF6p8Zx7JdRS7A"
        owner = OwnerFactory(
            stripe_subscription_id=stripe_subscription_id,
            plan=plan,
            plan_activated_users=[4, 6, 3],
            plan_user_count=9,
            stripe_customer_id=customer_id,
        )
        subscription_params = {
            "schedule_id": stripe_schedule_id,
            "start_date": 1489799420,
            "end_date": 1492477820,
            "quantity": 10,
            "name": plan,
            "id": 215,
            "plan": {
                "new_plan": "plan_pro_yearly",
                "new_quantity": 7,
                "subscription_id": "sub_123",
                "interval": "year",
            },
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)
        retrieve_customer_mock.return_value = {
            "id": "cus_HF6p8Zx7JdRS7A",
            "metadata": {"autorefunds_remaining": "1"},
        }
        self.stripe.delete_subscription(owner)
        schedule_release_mock.assert_called_once_with(stripe_schedule_id)
        retrieve_customer_mock.assert_called_once_with(owner.stripe_customer_id)
        cancel_sub_mock.assert_called_once_with(stripe_subscription_id)
        list_invoice_mock.assert_called_once_with(
            subscription=stripe_subscription_id,
            status="paid",
            created={"gte": 1458263420, "lt": 1489799420},
        )
        self.assertEqual(create_refund_mock.call_count, 2)
        modify_customer_mock.assert_called_once_with(
            owner.stripe_customer_id, balance=0, metadata={"autorefunds_remaining": "0"}
        )
        modify_sub_mock.assert_not_called()

        owner.refresh_from_db()
        assert owner.stripe_subscription_id == stripe_subscription_id
        assert owner.plan == plan
        assert owner.plan_activated_users == [4, 6, 3]
        assert owner.plan_user_count == 9

    @freeze_time("2017-03-19T00:00:00")
    @patch("services.billing.stripe.Customer.retrieve")
    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.Customer.modify")
    @patch("services.billing.stripe.Refund.create")
    @patch("services.billing.stripe.Invoice.list")
    @patch("services.billing.stripe.Subscription.cancel")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.SubscriptionSchedule.release")
    def test_delete_subscription_with_schedule_releases_schedule_and_cancels_subscription_immediately_with_grace_year_but_no_invoices_to_refund(
        self,
        schedule_release_mock,
        retrieve_subscription_mock,
        cancel_sub_mock,
        list_invoice_mock,
        create_refund_mock,
        modify_customer_mock,
        modify_sub_mock,
        retrieve_customer_mock,
    ):
        with open("./services/tests/samples/stripe_invoice.json") as f:
            stripe_invoice_response = json.load(f)
        for invoice in stripe_invoice_response["data"]:
            invoice["charge"] = None
        list_invoice_mock.return_value = stripe_invoice_response
        plan = PlanName.CODECOV_PRO_YEARLY.value
        stripe_subscription_id = "sub_1K77Y5GlVGuVgOrkJrLjRnne"
        stripe_schedule_id = "sub_sched_sch1K77Y5GlVGuVgOrkJrLjRnne"
        customer_id = "cus_HF6p8Zx7JdRS7A"
        owner = OwnerFactory(
            stripe_subscription_id=stripe_subscription_id,
            plan=plan,
            plan_activated_users=[4, 6, 3],
            plan_user_count=9,
            stripe_customer_id=customer_id,
        )
        subscription_params = {
            "schedule_id": stripe_schedule_id,
            "start_date": 1489799420,
            "end_date": 1492477820,
            "quantity": 10,
            "name": plan,
            "id": 215,
            "plan": {
                "new_plan": "plan_pro_yearly",
                "new_quantity": 7,
                "subscription_id": "sub_123",
                "interval": "year",
            },
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)
        retrieve_customer_mock.return_value = {
            "id": "cus_HF6p8Zx7JdRS7A",
            "metadata": {"autorefunds_remaining": "1"},
        }
        self.stripe.delete_subscription(owner)
        schedule_release_mock.assert_called_once_with(stripe_schedule_id)
        retrieve_customer_mock.assert_called_once_with(owner.stripe_customer_id)
        cancel_sub_mock.assert_called_once_with(stripe_subscription_id)
        list_invoice_mock.assert_called_once_with(
            subscription=stripe_subscription_id,
            status="paid",
            created={"gte": 1458263420, "lt": 1489799420},
        )
        create_refund_mock.assert_not_called()
        modify_customer_mock.assert_not_called()
        modify_sub_mock.assert_not_called()

        owner.refresh_from_db()
        assert owner.stripe_subscription_id == stripe_subscription_id
        assert owner.plan == plan
        assert owner.plan_activated_users == [4, 6, 3]
        assert owner.plan_user_count == 9

    @freeze_time("2017-03-19T00:00:00")
    @patch("services.billing.stripe.Customer.retrieve")
    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.Customer.modify")
    @patch("services.billing.stripe.Refund.create")
    @patch("services.billing.stripe.Invoice.list")
    @patch("services.billing.stripe.Subscription.cancel")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.SubscriptionSchedule.release")
    def test_delete_subscription_with_schedule_releases_schedule_and_cancels_subscription_at_end_of_billing_cycle_as_no_more_autorefunds_available(
        self,
        schedule_release_mock,
        retrieve_subscription_mock,
        cancel_sub_mock,
        list_invoice_mock,
        create_refund_mock,
        modify_customer_mock,
        modify_sub_mock,
        retrieve_customer_mock,
    ):
        with open("./services/tests/samples/stripe_invoice.json") as f:
            stripe_invoice_response = json.load(f)
        list_invoice_mock.return_value = stripe_invoice_response
        plan = PlanName.CODECOV_PRO_YEARLY.value
        stripe_subscription_id = "sub_1K77Y5GlVGuVgOrkJrLjRnne"
        stripe_schedule_id = "sub_sched_sch1K77Y5GlVGuVgOrkJrLjRnne"
        customer_id = "cus_HF6p8Zx7JdRS7A"
        owner = OwnerFactory(
            stripe_subscription_id=stripe_subscription_id,
            plan=plan,
            plan_activated_users=[4, 6, 3],
            plan_user_count=9,
            stripe_customer_id=customer_id,
        )
        subscription_params = {
            "schedule_id": stripe_schedule_id,
            "start_date": 1489799420,
            "end_date": 1492477820,
            "quantity": 10,
            "name": plan,
            "id": 215,
            "plan": {
                "new_plan": "plan_pro_yearly",
                "new_quantity": 7,
                "subscription_id": "sub_123",
                "interval": "year",
            },
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)
        retrieve_customer_mock.return_value = {
            "id": "cus_HF6p8Zx7JdRS7A",
            "metadata": {"autorefunds_remaining": "0"},
        }
        self.stripe.delete_subscription(owner)
        schedule_release_mock.assert_called_once_with(stripe_schedule_id)
        retrieve_customer_mock.assert_called_once_with(owner.stripe_customer_id)
        cancel_sub_mock.assert_not_called()
        create_refund_mock.assert_not_called()
        modify_customer_mock.assert_not_called()
        modify_sub_mock.assert_called_once_with(
            stripe_subscription_id,
            cancel_at_period_end=True,
            proration_behavior="none",
        )

        owner.refresh_from_db()
        assert owner.stripe_subscription_id == stripe_subscription_id
        assert owner.plan == plan
        assert owner.plan_activated_users == [4, 6, 3]
        assert owner.plan_user_count == 9

    @patch("logging.Logger.error")
    def test_modify_subscription_no_plan_found(
        self,
        log_error_mock,
    ):
        original_plan = PlanName.CODECOV_PRO_MONTHLY.value
        original_user_count = 10
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id="33043sdf",
        )

        desired_plan_name = "invalid plan"
        desired_user_count = 10
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}
        self.stripe.modify_subscription(owner, desired_plan)

        owner.refresh_from_db()
        assert owner.plan == original_plan
        assert owner.plan_user_count == original_user_count
        log_error_mock.assert_has_calls(
            [
                call(
                    f"Plan {desired_plan_name} not found",
                    extra=dict(owner_id=owner.ownerid),
                ),
            ]
        )

    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_without_schedule_increases_user_count_immediately(
        self,
        retrieve_subscription_mock,
        subscription_modify_mock,
    ):
        original_user_count = 10
        original_plan = PlanName.CODECOV_PRO_YEARLY.value
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id="33043sdf",
        )

        schedule_id = None
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 105,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)
        subscription_modify_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = PlanName.CODECOV_PRO_YEARLY.value
        desired_user_count = 20
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}
        self.stripe.modify_subscription(owner, desired_plan)

        self._assert_subscription_modify(
            subscription_modify_mock, owner, subscription_params, desired_plan
        )

        owner.refresh_from_db()
        assert owner.plan == desired_plan_name
        assert owner.plan_user_count == desired_user_count

    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_without_schedule_upgrades_plan_immediately(
        self,
        retrieve_subscription_mock,
        subscription_modify_mock,
    ):
        original_plan = PlanName.CODECOV_PRO_MONTHLY.value
        original_user_count = 10
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id="33043sdf",
        )

        schedule_id = None
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 101,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)
        subscription_modify_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = PlanName.CODECOV_PRO_YEARLY.value
        desired_user_count = 10
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}
        self.stripe.modify_subscription(owner, desired_plan)

        self._assert_subscription_modify(
            subscription_modify_mock, owner, subscription_params, desired_plan
        )

        owner.refresh_from_db()
        assert owner.plan == desired_plan_name
        assert owner.plan_user_count == desired_user_count

    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_payment_failure(
        self,
        retrieve_subscription_mock,
        subscription_modify_mock,
    ):
        original_user_count = 10
        original_plan = PlanName.CODECOV_PRO_YEARLY.value
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id="33043sdf",
            delinquent=False,
        )
        schedule_id = None
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 105,
        }
        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        subscription_response = {
            "id": 105,
            "object": "subscription",
            "application_fee_percent": None,
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
        subscription_modify_mock.return_value = MockFailedSubscriptionUpgrade(
            subscription_response
        )

        desired_plan_name = PlanName.CODECOV_PRO_YEARLY.value
        desired_user_count = 20
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}
        self.stripe.modify_subscription(owner, desired_plan)

        self._assert_subscription_modify(
            subscription_modify_mock, owner, subscription_params, desired_plan
        )

        # changes to plan are rejected, owner becomes delinquent
        owner.refresh_from_db()
        assert owner.plan == desired_plan_name
        assert owner.plan_user_count == original_user_count
        assert owner.delinquent == True

    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_payment_no_false_positives(
        self,
        retrieve_subscription_mock,
        subscription_modify_mock,
    ):
        original_user_count = 10
        original_plan = PlanName.CODECOV_PRO_YEARLY.value
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id="33043sdf",
            delinquent=False,
        )
        schedule_id = None
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 105,
        }
        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        subscription_response = {
            "id": 105,
            "object": "subscription",
            "application_fee_percent": None,
            "pending_update": {},
        }
        subscription_modify_mock.return_value = MockFailedSubscriptionUpgrade(
            subscription_response
        )

        desired_plan_name = PlanName.CODECOV_PRO_YEARLY.value
        desired_user_count = 20
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}
        self.stripe.modify_subscription(owner, desired_plan)

        self._assert_subscription_modify(
            subscription_modify_mock, owner, subscription_params, desired_plan
        )

        # plan is updated, owner is not delinquent
        owner.refresh_from_db()
        assert owner.plan == desired_plan_name
        assert owner.plan_user_count == desired_user_count
        assert owner.delinquent == False

    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_but_stripe_is_broken(
        self, retrieve_subscription_mock, subscription_modify_mock
    ):
        owner = OwnerFactory(
            plan=PlanName.CODECOV_PRO_YEARLY.value,
            plan_user_count=10,
            stripe_subscription_id="33043sdf",
            delinquent=False,
        )
        subscription_params = {
            "schedule_id": None,
            "start_date": 1639628096,
            "end_date": 1644107871,
            "quantity": 10,
            "name": PlanName.CODECOV_PRO_YEARLY.value,
            "id": 105,
        }
        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        subscription_modify_mock.side_effect = requests.exceptions.Timeout

        desired_plan = {"value": PlanName.CODECOV_PRO_YEARLY.value, "quantity": 100}
        with self.assertRaises(requests.exceptions.Timeout):
            # if stripe is erroring, it will pop up on sentry
            self.stripe.modify_subscription(owner, desired_plan)

        owner.refresh_from_db()
        assert owner.plan == PlanName.CODECOV_PRO_YEARLY.value
        assert owner.plan_user_count == 10
        assert owner.delinquent == False

    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_without_schedule_upgrades_plan_and_users_immediately(
        self,
        retrieve_subscription_mock,
        subscription_modify_mock,
    ):
        original_user_count = 10
        original_plan = PlanName.CODECOV_PRO_MONTHLY.value
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id="33043sdf",
        )

        schedule_id = None
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 102,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)
        subscription_modify_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = PlanName.CODECOV_PRO_YEARLY.value
        desired_user_count = 15
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}
        self.stripe.modify_subscription(owner, desired_plan)

        self._assert_subscription_modify(
            subscription_modify_mock, owner, subscription_params, desired_plan
        )

        owner.refresh_from_db()
        assert owner.plan == desired_plan_name
        assert owner.plan_user_count == desired_user_count

    @patch("services.billing.stripe.SubscriptionSchedule.create")
    @patch("services.billing.stripe.SubscriptionSchedule.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_without_schedule_adds_schedule_when_user_count_decreases(
        self, retrieve_subscription_mock, schedule_modify_mock, create_mock
    ):
        original_user_count = 14
        original_plan = PlanName.CODECOV_PRO_MONTHLY.value
        stripe_subscription_id = "33043sdf"
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id=stripe_subscription_id,
        )

        schedule_id = None
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 104,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = PlanName.CODECOV_PRO_MONTHLY.value
        desired_user_count = 8
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}

        self.stripe.modify_subscription(owner, desired_plan)

        create_mock.assert_called_once_with(from_subscription=stripe_subscription_id)
        schedule_id = create_mock.return_value._mock_children["id"]

        self._assert_schedule_modify(
            schedule_modify_mock, owner, subscription_params, desired_plan, schedule_id
        )

        owner.refresh_from_db()
        assert owner.plan == original_plan
        assert owner.plan_user_count == original_user_count

    @patch("services.billing.stripe.SubscriptionSchedule.create")
    @patch("services.billing.stripe.SubscriptionSchedule.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_without_schedule_adds_schedule_when_plan_downgrades(
        self, retrieve_subscription_mock, schedule_modify_mock, create_mock
    ):
        original_user_count = 20
        original_plan = PlanName.CODECOV_PRO_YEARLY.value
        stripe_subscription_id = "33043sdf"
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id=stripe_subscription_id,
        )

        schedule_id = None
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 106,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = PlanName.CODECOV_PRO_MONTHLY.value
        desired_user_count = 20
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}

        self.stripe.modify_subscription(owner, desired_plan)

        create_mock.assert_called_once_with(from_subscription=stripe_subscription_id)
        schedule_id = create_mock.return_value._mock_children["id"]

        self._assert_schedule_modify(
            schedule_modify_mock, owner, subscription_params, desired_plan, schedule_id
        )

        owner.refresh_from_db()
        assert owner.plan == original_plan
        assert owner.plan_user_count == original_user_count

    @patch("services.billing.stripe.SubscriptionSchedule.create")
    @patch("services.billing.stripe.SubscriptionSchedule.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_without_schedule_adds_schedule_when_plan_and_count_downgrades(
        self, retrieve_subscription_mock, schedule_modify_mock, create_mock
    ):
        original_user_count = 16
        original_plan = PlanName.CODECOV_PRO_YEARLY.value
        stripe_subscription_id = "33043sdf"
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id=stripe_subscription_id,
        )

        schedule_id = None
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 107,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = PlanName.CODECOV_PRO_MONTHLY.value
        desired_user_count = 7
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}

        self.stripe.modify_subscription(owner, desired_plan)

        create_mock.assert_called_once_with(from_subscription=stripe_subscription_id)
        schedule_id = create_mock.return_value._mock_children["id"]

        self._assert_schedule_modify(
            schedule_modify_mock, owner, subscription_params, desired_plan, schedule_id
        )

        owner.refresh_from_db()
        assert owner.plan == original_plan
        assert owner.plan_user_count == original_user_count

    @patch("services.billing.stripe.SubscriptionSchedule.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_with_schedule_modifies_schedule_when_user_count_decreases(
        self, retrieve_subscription_mock, schedule_modify_mock
    ):
        original_user_count = 13
        original_plan = PlanName.CODECOV_PRO_MONTHLY.value
        stripe_subscription_id = "33043sdf"
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id=stripe_subscription_id,
        )

        schedule_id = "sub_sched_1K77Y5GlVGuVgOrkJrLjRnne"
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 108,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = PlanName.CODECOV_PRO_MONTHLY.value
        desired_user_count = 9
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}

        self.stripe.modify_subscription(owner, desired_plan)

        self._assert_schedule_modify(
            schedule_modify_mock, owner, subscription_params, desired_plan, schedule_id
        )

        owner.refresh_from_db()
        assert owner.plan == original_plan
        assert owner.plan_user_count == original_user_count

    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.SubscriptionSchedule.release")
    def test_modify_subscription_with_schedule_modifies_schedule_when_user_count_increases(
        self,
        schedule_release_mock,
        retrieve_subscription_mock,
        subscription_modify_mock,
    ):
        original_user_count = 17
        original_plan = PlanName.CODECOV_PRO_MONTHLY.value
        stripe_subscription_id = "33043sdf"
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id=stripe_subscription_id,
        )

        desired_plan_name = PlanName.CODECOV_PRO_MONTHLY.value
        desired_user_count = 26

        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}
        schedule_id = "sub_sched_1K77Y5GlVGuVgOrkJrLjRnne"
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 109,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)
        subscription_modify_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = PlanName.CODECOV_PRO_MONTHLY.value
        desired_user_count = 26
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}
        self.stripe.modify_subscription(owner, desired_plan)
        schedule_release_mock.assert_called_once_with(schedule_id)
        self._assert_subscription_modify(
            subscription_modify_mock, owner, subscription_params, desired_plan
        )

        owner.refresh_from_db()
        assert owner.plan == desired_plan_name
        assert owner.plan_user_count == desired_user_count

    @patch("services.billing.stripe.SubscriptionSchedule.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_modify_subscription_with_schedule_modifies_schedule_when_plan_downgrades(
        self, retrieve_subscription_mock, schedule_modify_mock
    ):
        original_user_count = 15
        original_plan = PlanName.CODECOV_PRO_YEARLY.value
        stripe_subscription_id = "33043sdf"
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id=stripe_subscription_id,
        )

        schedule_id = "sub_sched_1K77Y5GlVGuVgOrkJrLjRn2e"
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": Plan.objects.get(name=original_plan).stripe_id,
            "id": 110,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = PlanName.CODECOV_PRO_MONTHLY.value
        desired_user_count = 15
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}

        self.stripe.modify_subscription(owner, desired_plan)

        self._assert_schedule_modify(
            schedule_modify_mock, owner, subscription_params, desired_plan, schedule_id
        )

        owner.refresh_from_db()
        assert owner.plan == original_plan
        assert owner.plan_user_count == original_user_count

    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.SubscriptionSchedule.release")
    def test_modify_subscription_with_schedule_releases_schedule_when_plan_upgrades(
        self,
        schedule_release_mock,
        retrieve_subscription_mock,
        subscription_modify_mock,
    ):
        original_user_count = 15
        original_plan = PlanName.CODECOV_PRO_MONTHLY.value
        stripe_subscription_id = "33043sdf"
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id=stripe_subscription_id,
        )

        schedule_id = "sub_sched_1K77Y5GlVGuVgOrkJrLjRn2e"
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 111,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)
        subscription_modify_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = PlanName.CODECOV_PRO_YEARLY.value
        desired_user_count = 15
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}

        self.stripe.modify_subscription(owner, desired_plan)
        schedule_release_mock.assert_called_once_with(schedule_id)
        self._assert_subscription_modify(
            subscription_modify_mock, owner, subscription_params, desired_plan
        )

        owner.refresh_from_db()
        assert owner.plan == desired_plan_name
        assert owner.plan_user_count == desired_user_count

    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.SubscriptionSchedule.release")
    def test_modify_subscription_with_schedule_releases_schedule_when_plan_upgrades_and_count_decreases(
        self,
        schedule_release_mock,
        retrieve_subscription_mock,
        subscription_modify_mock,
    ):
        original_user_count = 15
        original_plan = PlanName.CODECOV_PRO_MONTHLY.value
        stripe_subscription_id = "33043sdf"
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id=stripe_subscription_id,
        )

        schedule_id = "sub_sched_1K77Y5GlVGuVgOrkJrLjRn2e"
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 112,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)
        subscription_modify_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = PlanName.CODECOV_PRO_YEARLY.value
        desired_user_count = 10
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}
        self.stripe.modify_subscription(owner, desired_plan)
        schedule_release_mock.assert_called_once_with(schedule_id)
        self._assert_subscription_modify(
            subscription_modify_mock, owner, subscription_params, desired_plan
        )

        owner.refresh_from_db()
        assert owner.plan == desired_plan_name
        assert owner.plan_user_count == desired_user_count

    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.SubscriptionSchedule.release")
    def test_modify_subscription_with_schedule_releases_schedule_when_plan_downgrades_and_count_increases(
        self,
        schedule_release_mock,
        retrieve_subscription_mock,
        subscription_modify_mock,
    ):
        original_user_count = 15
        original_plan = PlanName.CODECOV_PRO_YEARLY.value
        stripe_subscription_id = "33043sdf"
        owner = OwnerFactory(
            plan=original_plan,
            plan_user_count=original_user_count,
            stripe_subscription_id=stripe_subscription_id,
        )

        schedule_id = "sub_sched_1K77Y5GlVGuVgOrkJrLjRn2e"
        current_subscription_start_date = 1639628096
        current_subscription_end_date = 1644107871
        subscription_params = {
            "schedule_id": schedule_id,
            "start_date": current_subscription_start_date,
            "end_date": current_subscription_end_date,
            "quantity": original_user_count,
            "name": original_plan,
            "id": 113,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)
        subscription_modify_mock.return_value = MockSubscription(subscription_params)

        desired_plan_name = PlanName.CODECOV_PRO_MONTHLY.value
        desired_user_count = 20
        desired_plan = {"value": desired_plan_name, "quantity": desired_user_count}

        self.stripe.modify_subscription(owner, desired_plan)
        schedule_release_mock.assert_called_once_with(schedule_id)
        self._assert_subscription_modify(
            subscription_modify_mock, owner, subscription_params, desired_plan
        )

        owner.refresh_from_db()
        assert owner.plan == desired_plan_name
        assert owner.plan_user_count == desired_user_count

    def test_get_proration_params(self):
        # Test same plan, increased users
        owner = OwnerFactory(plan=PlanName.CODECOV_PRO_YEARLY.value, plan_user_count=10)
        plan = Plan.objects.get(name=PlanName.CODECOV_PRO_YEARLY.value)
        assert (
            self.stripe._get_proration_params(
                owner=owner, desired_plan_info=plan, desired_quantity=14
            )
            == "always_invoice"
        )

        # Test same plan, decrease users
        owner = OwnerFactory(plan=PlanName.CODECOV_PRO_YEARLY.value, plan_user_count=20)
        assert (
            self.stripe._get_proration_params(
                owner=owner, desired_plan_info=plan, desired_quantity=14
            )
            == "none"
        )

        # Test going from monthly to yearly
        owner = OwnerFactory(
            plan=PlanName.CODECOV_PRO_MONTHLY.value, plan_user_count=20
        )
        assert (
            self.stripe._get_proration_params(
                owner=owner, desired_plan_info=plan, desired_quantity=14
            )
            == "always_invoice"
        )

        # monthly to Sentry monthly plan
        owner = OwnerFactory(
            plan=PlanName.CODECOV_PRO_MONTHLY.value, plan_user_count=20
        )
        plan = Plan.objects.get(name=PlanName.SENTRY_MONTHLY.value)
        assert (
            self.stripe._get_proration_params(
                owner=owner, desired_plan_info=plan, desired_quantity=19
            )
            == "none"
        )
        assert (
            self.stripe._get_proration_params(
                owner=owner, desired_plan_info=plan, desired_quantity=20
            )
            == "always_invoice"
        )
        assert (
            self.stripe._get_proration_params(
                owner=owner, desired_plan_info=plan, desired_quantity=21
            )
            == "always_invoice"
        )

        # yearly to Sentry monthly plan
        owner = OwnerFactory(plan=PlanName.CODECOV_PRO_YEARLY.value, plan_user_count=20)
        plan = Plan.objects.get(name=PlanName.SENTRY_MONTHLY.value)
        assert (
            self.stripe._get_proration_params(
                owner=owner, desired_plan_info=plan, desired_quantity=19
            )
            == "none"
        )
        assert (
            self.stripe._get_proration_params(
                owner=owner, desired_plan_info=plan, desired_quantity=20
            )
            == "none"
        )
        assert (
            self.stripe._get_proration_params(
                owner=owner, desired_plan_info=plan, desired_quantity=21
            )
            == "always_invoice"
        )

        # monthly to Sentry monthly plan
        owner = OwnerFactory(
            plan=PlanName.CODECOV_PRO_MONTHLY.value, plan_user_count=20
        )
        plan = Plan.objects.get(name=PlanName.SENTRY_MONTHLY.value)
        assert (
            self.stripe._get_proration_params(
                owner=owner, desired_plan_info=plan, desired_quantity=19
            )
            == "none"
        )
        assert (
            self.stripe._get_proration_params(
                owner=owner, desired_plan_info=plan, desired_quantity=20
            )
            == "always_invoice"
        )
        assert (
            self.stripe._get_proration_params(
                owner=owner, desired_plan_info=plan, desired_quantity=21
            )
            == "always_invoice"
        )

        # yearly to Sentry yearly plan
        owner = OwnerFactory(plan=PlanName.CODECOV_PRO_YEARLY.value, plan_user_count=20)
        plan = Plan.objects.get(name=PlanName.SENTRY_YEARLY.value)
        assert (
            self.stripe._get_proration_params(
                owner=owner, desired_plan_info=plan, desired_quantity=19
            )
            == "none"
        )
        assert (
            self.stripe._get_proration_params(
                owner=owner, desired_plan_info=plan, desired_quantity=20
            )
            == "always_invoice"
        )
        assert (
            self.stripe._get_proration_params(
                owner=owner, desired_plan_info=plan, desired_quantity=21
            )
            == "always_invoice"
        )

        # monthly to Sentry yearly plan
        owner = OwnerFactory(
            plan=PlanName.CODECOV_PRO_MONTHLY.value, plan_user_count=20
        )
        plan = Plan.objects.get(name=PlanName.SENTRY_YEARLY.value)
        assert (
            self.stripe._get_proration_params(
                owner=owner, desired_plan_info=plan, desired_quantity=19
            )
            == "always_invoice"
        )
        assert (
            self.stripe._get_proration_params(
                owner=owner, desired_plan_info=plan, desired_quantity=20
            )
            == "always_invoice"
        )
        assert (
            self.stripe._get_proration_params(
                owner=owner, desired_plan_info=plan, desired_quantity=21
            )
            == "always_invoice"
        )

        # Team to Sentry
        owner = OwnerFactory(plan=PlanName.TEAM_MONTHLY.value, plan_user_count=10)
        plan = Plan.objects.get(name=PlanName.SENTRY_MONTHLY.value)
        assert (
            self.stripe._get_proration_params(
                owner=owner, desired_plan_info=plan, desired_quantity=10
            )
            == "always_invoice"
        )

        # Team to Pro
        owner = OwnerFactory(plan=PlanName.TEAM_MONTHLY.value, plan_user_count=10)
        plan = Plan.objects.get(name=PlanName.CODECOV_PRO_MONTHLY.value)
        assert (
            self.stripe._get_proration_params(
                owner=owner, desired_plan_info=plan, desired_quantity=10
            )
            == "always_invoice"
        )

        # Sentry to Team
        owner = OwnerFactory(plan=PlanName.SENTRY_MONTHLY.value, plan_user_count=10)
        plan = Plan.objects.get(name=PlanName.TEAM_MONTHLY.value)
        assert (
            self.stripe._get_proration_params(
                owner=owner, desired_plan_info=plan, desired_quantity=10
            )
            == "none"
        )

        # Sentry to Pro
        owner = OwnerFactory(
            plan=PlanName.CODECOV_PRO_MONTHLY.value, plan_user_count=10
        )
        plan = Plan.objects.get(name=PlanName.TEAM_MONTHLY.value)
        assert (
            self.stripe._get_proration_params(
                owner=owner, desired_plan_info=plan, desired_quantity=10
            )
            == "none"
        )

    @patch("services.billing.stripe.checkout.Session.create")
    def test_create_checkout_session_with_no_stripe_customer_id(
        self, create_checkout_session_mock
    ):
        stripe_customer_id = None
        owner = OwnerFactory(
            service=Service.GITHUB.value,
            stripe_customer_id=stripe_customer_id,
        )
        expected_id = "fkkgosd"
        create_checkout_session_mock.return_value = {"id": expected_id}
        desired_quantity = 25
        desired_plan = {
            "value": PlanName.CODECOV_PRO_MONTHLY.value,
            "quantity": desired_quantity,
        }
        plan = Plan.objects.get(name=desired_plan["value"])

        assert self.stripe.create_checkout_session(owner, desired_plan) == expected_id

        create_checkout_session_mock.assert_called_once_with(
            billing_address_collection="required",
            payment_method_configuration=settings.STRIPE_PAYMENT_METHOD_CONFIGURATION_ID,
            payment_method_collection="if_required",
            client_reference_id=str(owner.ownerid),
            customer=None,
            success_url=f"{settings.CODECOV_DASHBOARD_URL}/plan/gh/{owner.username}?success",
            cancel_url=f"{settings.CODECOV_DASHBOARD_URL}/plan/gh/{owner.username}?cancel",
            mode="subscription",
            line_items=[
                {
                    "price": plan.stripe_id,
                    "quantity": desired_quantity,
                }
            ],
            subscription_data={
                "metadata": {
                    "service": owner.service,
                    "obo_organization": owner.ownerid,
                    "username": owner.username,
                    "obo_name": self.user.name,
                    "obo_email": self.user.email,
                    "obo": self.user.ownerid,
                },
            },
            tax_id_collection={"enabled": True},
            customer_update=None,
        )

    @patch("services.billing.stripe.checkout.Session.create")
    def test_create_checkout_session_with_stripe_customer_id(
        self, create_checkout_session_mock
    ):
        stripe_customer_id = "test-cusa78723hb4@"
        owner = OwnerFactory(
            service=Service.GITHUB.value,
            stripe_customer_id=stripe_customer_id,
        )
        expected_id = "fkkgosd"
        create_checkout_session_mock.return_value = {"id": expected_id}
        desired_quantity = 25
        desired_plan = {
            "value": PlanName.CODECOV_PRO_MONTHLY.value,
            "quantity": desired_quantity,
        }

        assert self.stripe.create_checkout_session(owner, desired_plan) == expected_id

        plan = Plan.objects.get(name=desired_plan["value"])

        create_checkout_session_mock.assert_called_once_with(
            billing_address_collection="required",
            payment_method_configuration=settings.STRIPE_PAYMENT_METHOD_CONFIGURATION_ID,
            payment_method_collection="if_required",
            client_reference_id=str(owner.ownerid),
            customer=owner.stripe_customer_id,
            success_url=f"{settings.CODECOV_DASHBOARD_URL}/plan/gh/{owner.username}?success",
            cancel_url=f"{settings.CODECOV_DASHBOARD_URL}/plan/gh/{owner.username}?cancel",
            mode="subscription",
            line_items=[
                {
                    "price": plan.stripe_id,
                    "quantity": desired_quantity,
                }
            ],
            subscription_data={
                "metadata": {
                    "service": owner.service,
                    "obo_organization": owner.ownerid,
                    "username": owner.username,
                    "obo_name": self.user.name,
                    "obo_email": self.user.email,
                    "obo": self.user.ownerid,
                },
            },
            tax_id_collection={"enabled": True},
            customer_update={"name": "auto", "address": "auto"},
        )

    @patch("logging.Logger.error")
    @patch("services.billing.stripe.checkout.Session.create")
    def test_create_checkout_session_with_invalid_plan(
        self, create_checkout_session_mock, logger_error_mock
    ):
        stripe_customer_id = "test-cusa78723hb4@"
        owner = OwnerFactory(
            service=Service.GITHUB.value,
            stripe_customer_id=stripe_customer_id,
        )
        desired_quantity = 25
        desired_plan = {
            "value": "invalid_plan",
            "quantity": desired_quantity,
        }

        self.stripe.create_checkout_session(owner, desired_plan)

        create_checkout_session_mock.assert_not_called()
        logger_error_mock.assert_called_once_with(
            f"Plan {desired_plan['value']} not found",
            extra=dict(
                owner_id=owner.ownerid,
            ),
        )

    def test_get_subscription_when_no_subscription(self):
        owner = OwnerFactory(stripe_subscription_id=None)
        assert self.stripe.get_subscription(owner) is None

    @patch("services.billing.stripe.Subscription.retrieve")
    def test_get_subscription_returns_stripe_data(self, subscription_retrieve_mock):
        owner = OwnerFactory(stripe_subscription_id="abc")
        # only including fields relevant to implementation
        stripe_data_subscription = {"doesnt": "matter"}
        subscription_retrieve_mock.return_value = stripe_data_subscription
        assert self.stripe.get_subscription(owner) == stripe_data_subscription
        subscription_retrieve_mock.assert_called_once_with(
            owner.stripe_subscription_id,
            expand=[
                "latest_invoice",
                "customer",
                "customer.invoice_settings.default_payment_method",
                "customer.tax_ids",
            ],
        )

    def test_update_payment_method_when_no_subscription(self):
        owner = OwnerFactory(stripe_subscription_id=None)
        assert self.stripe.update_payment_method(owner, "abc") is None

    @patch("services.billing.stripe.PaymentMethod.attach")
    @patch("services.billing.stripe.Customer.modify")
    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.StripeService._is_unverified_payment_method")
    def test_update_payment_method(
        self,
        is_unverified_mock,
        modify_sub_mock,
        modify_customer_mock,
        attach_payment_mock,
    ):
        payment_method_id = "pm_1234567"
        subscription_id = "sub_abc"
        customer_id = "cus_abc"
        owner = OwnerFactory(
            stripe_subscription_id=subscription_id, stripe_customer_id=customer_id
        )
        is_unverified_mock.return_value = False
        self.stripe.update_payment_method(owner, payment_method_id)
        attach_payment_mock.assert_called_once_with(
            payment_method_id, customer=customer_id
        )
        modify_customer_mock.assert_called_once_with(
            customer_id, invoice_settings={"default_payment_method": payment_method_id}
        )

        modify_sub_mock.assert_called_once_with(
            subscription_id, default_payment_method=payment_method_id
        )

    @patch("services.billing.stripe.PaymentMethod.attach")
    @patch("services.billing.stripe.Customer.modify")
    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.PaymentMethod.retrieve")
    @patch("services.billing.stripe.SetupIntent.list")
    def test_update_payment_method_with_unverified_payment_method(
        self,
        setup_intent_list_mock,
        payment_method_retrieve_mock,
        modify_sub_mock,
        modify_customer_mock,
        attach_payment_mock,
    ):
        # Define the mock return values
        setup_intent_list_mock.return_value = MagicMock(
            data=[
                MagicMock(
                    status="requires_action",
                    next_action=MagicMock(
                        type="verify_with_microdeposits",
                        verify_with_microdeposits=MagicMock(
                            hosted_verification_url="https://verify.stripe.com/1"
                        ),
                    ),
                )
            ]
        )
        payment_method_retrieve_mock.return_value = MagicMock(
            type="us_bank_account",
            us_bank_account=MagicMock(
                status="requires_action",
                next_action=MagicMock(
                    type="verify_with_microdeposits",
                    verify_with_microdeposits=MagicMock(
                        hosted_verification_url="https://verify.stripe.com/1"
                    ),
                ),
            ),
        )
        modify_sub_mock.return_value = MagicMock()
        modify_customer_mock.return_value = MagicMock()
        attach_payment_mock.return_value = MagicMock()

        # Create a mock owner object
        subscription_id = "sub_abc"
        customer_id = "cus_abc"
        owner = OwnerFactory(
            stripe_subscription_id=subscription_id, stripe_customer_id=customer_id
        )

        result = self.stripe.update_payment_method(owner, "abc")

        assert result is None
        assert payment_method_retrieve_mock.called
        assert setup_intent_list_mock.called
        assert not attach_payment_mock.called
        assert not modify_customer_mock.called
        assert not modify_sub_mock.called

    def test_update_email_address_with_invalid_email(self):
        owner = OwnerFactory(stripe_subscription_id=None)
        assert self.stripe.update_email_address(owner, "not-an-email") is None

    def test_update_email_address_when_no_subscription(self):
        owner = OwnerFactory(stripe_subscription_id=None)
        assert self.stripe.update_email_address(owner, "test@gmail.com") is None

    @patch("services.billing.stripe.Customer.modify")
    def test_update_email_address(self, modify_customer_mock):
        subscription_id = "sub_abc"
        customer_id = "cus_abc"
        email = "test@gmail.com"
        owner = OwnerFactory(
            stripe_subscription_id=subscription_id, stripe_customer_id=customer_id
        )
        self.stripe.update_email_address(owner, "test@gmail.com")
        modify_customer_mock.assert_called_once_with(customer_id, email=email)

    @patch("logging.Logger.error")
    def test_update_billing_address_with_invalid_address(self, log_error_mock):
        owner = OwnerFactory(stripe_customer_id="123", stripe_subscription_id="123")
        assert self.stripe.update_billing_address(owner, "John Doe", "gabagool") is None
        log_error_mock.assert_called_with(
            "Unable to update billing address for customer",
            extra={
                "customer_id": "123",
                "subscription_id": "123",
            },
        )

    def test_update_billing_address_when_no_customer_id(self):
        owner = OwnerFactory(stripe_customer_id=None)
        assert (
            self.stripe.update_billing_address(
                owner,
                name="John Doe",
                billing_address={
                    "line1": "45 Fremont St.",
                    "line2": "",
                    "city": "San Francisco",
                    "state": "CA",
                    "country": "US",
                    "postal_code": "94105",
                },
            )
            is None
        )

    @patch("services.billing.stripe.Customer.retrieve")
    @patch("services.billing.stripe.PaymentMethod.modify")
    @patch("services.billing.stripe.Customer.modify")
    def test_update_billing_address(
        self, modify_customer_mock, modify_payment_mock, retrieve_customer_mock
    ):
        subscription_id = "sub_abc"
        customer_id = "cus_abc"
        owner = OwnerFactory(
            stripe_subscription_id=subscription_id, stripe_customer_id=customer_id
        )
        billing_address = {
            "line1": "45 Fremont St.",
            "line2": "",
            "city": "San Francisco",
            "state": "CA",
            "country": "US",
            "postal_code": "94105",
        }
        self.stripe.update_billing_address(
            owner,
            name="John Doe",
            billing_address=billing_address,
        )

        retrieve_customer_mock.assert_called_once()
        modify_payment_mock.assert_called_once()
        modify_customer_mock.assert_called_once_with(
            customer_id, address=billing_address
        )

    @patch("services.billing.stripe.Invoice.retrieve")
    def test_get_invoice_not_found(self, retrieve_invoice_mock):
        invoice_id = "abc"
        retrieve_invoice_mock.side_effect = InvalidRequestError(
            message="not found", param=invoice_id
        )
        assert self.stripe.get_invoice(OwnerFactory(), invoice_id) is None
        retrieve_invoice_mock.assert_called_once_with(invoice_id)

    @patch("services.billing.stripe.Invoice.retrieve")
    def test_get_invoice_customer_dont_match(self, retrieve_invoice_mock):
        owner = OwnerFactory(stripe_customer_id="something_very_very_random_cus_abc")
        invoice_id = "abc"
        invoice = {"invoice_id": "abc", "customer": "cus_abc"}
        retrieve_invoice_mock.return_value = invoice
        assert self.stripe.get_invoice(owner, invoice_id) is None
        retrieve_invoice_mock.assert_called_once_with(invoice_id)

    @patch("services.billing.stripe.Invoice.retrieve")
    def test_get_invoice(self, retrieve_invoice_mock):
        customer_id = "cus_abc"
        owner = OwnerFactory(stripe_customer_id=customer_id)
        invoice_id = "abc"
        invoice = {"invoice_id": "abc", "customer": customer_id}
        retrieve_invoice_mock.return_value = invoice
        assert self.stripe.get_invoice(owner, invoice_id) == invoice
        retrieve_invoice_mock.assert_called_once_with(invoice_id)

    @patch("services.billing.stripe.Coupon.create")
    @patch("services.billing.stripe.Customer.modify")
    def test_apply_cancellation_discount(
        self, customer_modify_mock, coupon_create_mock
    ):
        coupon_create_mock.return_value = MagicMock(id="test-coupon-id")

        owner = OwnerFactory(
            stripe_subscription_id="test-subscription-id",
            stripe_customer_id="test-customer-id",
            plan="users-pr-inappm",
        )
        self.stripe.apply_cancellation_discount(owner)

        coupon_create_mock.assert_called_once_with(
            percent_off=30.0,
            duration="repeating",
            duration_in_months=6,
            name="30% off for 6 months",
            max_redemptions=1,
            metadata={
                "ownerid": owner.ownerid,
                "username": owner.username,
                "email": owner.email,
                "name": owner.name,
            },
        )
        customer_modify_mock.assert_called_once_with(
            "test-customer-id",
            coupon="test-coupon-id",
        )

        owner.refresh_from_db()
        assert owner.stripe_coupon_id == "test-coupon-id"

    @patch("services.billing.stripe.Coupon.create")
    @patch("services.billing.stripe.Customer.modify")
    def test_apply_cancellation_discount_yearly(
        self, customer_modify_mock, coupon_create_mock
    ):
        owner = OwnerFactory(
            stripe_customer_id="test-customer-id",
            stripe_subscription_id=None,
            plan="users-inappy",
        )
        self.stripe.apply_cancellation_discount(owner)

        assert not customer_modify_mock.called
        assert not coupon_create_mock.called
        assert owner.stripe_coupon_id is None

    @patch("services.billing.stripe.Coupon.create")
    @patch("services.billing.stripe.Customer.modify")
    def test_apply_cancellation_discount_no_subscription(
        self, customer_modify_mock, coupon_create_mock
    ):
        owner = OwnerFactory(
            stripe_customer_id="test-customer-id",
            stripe_subscription_id=None,
        )
        self.stripe.apply_cancellation_discount(owner)

        assert not customer_modify_mock.called
        assert not coupon_create_mock.called
        assert owner.stripe_coupon_id is None

    @patch("services.billing.stripe.Coupon.create")
    @patch("services.billing.stripe.Customer.modify")
    def test_apply_cancellation_discount_existing_coupon(
        self, customer_modify_mock, coupon_create_mock
    ):
        owner = OwnerFactory(
            stripe_customer_id="test-customer-id",
            stripe_subscription_id="test-subscription-id",
            stripe_coupon_id="test-coupon-id",
        )
        self.stripe.apply_cancellation_discount(owner)

        assert not customer_modify_mock.called
        assert not coupon_create_mock.called

    @patch("services.billing.stripe.SetupIntent.create")
    def test_create_setup_intent(self, setup_intent_create_mock):
        owner = OwnerFactory(stripe_customer_id="test-customer-id")
        setup_intent_create_mock.return_value = {"client_secret": "test-client-secret"}
        resp = self.stripe.create_setup_intent(owner)
        assert resp["client_secret"] == "test-client-secret"

    @patch("services.billing.stripe.PaymentIntent.list")
    @patch("services.billing.stripe.SetupIntent.list")
    def test_get_unverified_payment_methods(
        self, setup_intent_list_mock, payment_intent_list_mock
    ):
        owner = OwnerFactory(stripe_customer_id="test-customer-id")
        payment_intent = PaymentIntent.construct_from(
            {
                "id": "pi_123",
                "payment_method": "pm_123",
                "next_action": {
                    "type": "verify_with_microdeposits",
                    "verify_with_microdeposits": {
                        "hosted_verification_url": "https://verify.stripe.com/1"
                    },
                },
            },
            "fake_api_key",
        )

        setup_intent = SetupIntent.construct_from(
            {
                "id": "si_123",
                "payment_method": "pm_456",
                "next_action": {
                    "type": "verify_with_microdeposits",
                    "verify_with_microdeposits": {
                        "hosted_verification_url": "https://verify.stripe.com/2"
                    },
                },
            },
            "fake_api_key",
        )

        payment_intent_list_mock.return_value.data = [payment_intent]
        payment_intent_list_mock.return_value.has_more = False
        setup_intent_list_mock.return_value.data = [setup_intent]
        setup_intent_list_mock.return_value.has_more = False

        expected = [
            {
                "payment_method_id": "pm_123",
                "hosted_verification_url": "https://verify.stripe.com/1",
            },
            {
                "payment_method_id": "pm_456",
                "hosted_verification_url": "https://verify.stripe.com/2",
            },
        ]
        assert self.stripe.get_unverified_payment_methods(owner) == expected

    @patch("services.billing.stripe.PaymentIntent.list")
    @patch("services.billing.stripe.SetupIntent.list")
    def test_get_unverified_payment_methods_pagination(
        self, setup_intent_list_mock, payment_intent_list_mock
    ):
        owner = OwnerFactory(stripe_customer_id="test-customer-id")

        # Create 42 payment intents with only 2 having microdeposits verification
        payment_intents = []
        for i in range(42):
            next_action = None
            if i in [0, 41]:  # First and last have verification
                next_action = {
                    "type": "verify_with_microdeposits",
                    "verify_with_microdeposits": {
                        "hosted_verification_url": f"https://verify.stripe.com/pi_{i}"
                    },
                }
            payment_intents.append(
                PaymentIntent.construct_from(
                    {
                        "id": f"pi_{i}",
                        "payment_method": f"pm_pi_{i}",
                        "next_action": next_action,
                    },
                    "fake_api_key",
                )
            )

        # Create 42 setup intents with only 2 having microdeposits verification
        setup_intents = []
        for i in range(42):
            next_action = None
            if i in [0, 41]:  # First and last have verification
                next_action = {
                    "type": "verify_with_microdeposits",
                    "verify_with_microdeposits": {
                        "hosted_verification_url": f"https://verify.stripe.com/si_{i}"
                    },
                }
            setup_intents.append(
                SetupIntent.construct_from(
                    {
                        "id": f"si_{i}",
                        "payment_method": f"pm_si_{i}",
                        "next_action": next_action,
                    },
                    "fake_api_key",
                )
            )

        # Split into pages of 20
        payment_intent_pages = [
            type(
                "obj",
                (object,),
                {
                    "data": payment_intents[i : i + 20],
                    "has_more": i + 20 < len(payment_intents),
                },
            )
            for i in range(0, len(payment_intents), 20)
        ]

        setup_intent_pages = [
            type(
                "obj",
                (object,),
                {
                    "data": setup_intents[i : i + 20],
                    "has_more": i + 20 < len(setup_intents),
                },
            )
            for i in range(0, len(setup_intents), 20)
        ]

        payment_intent_list_mock.side_effect = payment_intent_pages
        setup_intent_list_mock.side_effect = setup_intent_pages

        expected = [
            {
                "payment_method_id": "pm_pi_0",
                "hosted_verification_url": "https://verify.stripe.com/pi_0",
            },
            {
                "payment_method_id": "pm_pi_41",
                "hosted_verification_url": "https://verify.stripe.com/pi_41",
            },
            {
                "payment_method_id": "pm_si_0",
                "hosted_verification_url": "https://verify.stripe.com/si_0",
            },
            {
                "payment_method_id": "pm_si_41",
                "hosted_verification_url": "https://verify.stripe.com/si_41",
            },
        ]

        result = self.stripe.get_unverified_payment_methods(owner)
        assert result == expected
        assert len(result) == 4  # Verify we got exactly 4 results

        # Verify pagination calls
        payment_intent_calls = [
            call(customer="test-customer-id", limit=20, starting_after=None),
            call(customer="test-customer-id", limit=20, starting_after="pi_19"),
            call(customer="test-customer-id", limit=20, starting_after="pi_39"),
        ]
        setup_intent_calls = [
            call(customer="test-customer-id", limit=20, starting_after=None),
            call(customer="test-customer-id", limit=20, starting_after="si_19"),
            call(customer="test-customer-id", limit=20, starting_after="si_39"),
        ]

        payment_intent_list_mock.assert_has_calls(payment_intent_calls)
        setup_intent_list_mock.assert_has_calls(setup_intent_calls)


class MockPaymentService(AbstractPaymentService):
    def list_filtered_invoices(self, owner, limit=10):
        return f"{owner.ownerid} {limit}"

    def get_invoice(self, owner, id):
        pass

    def delete_subscription(self, owner):
        pass

    def modify_subscription(self, owner, plan):
        pass

    def create_checkout_session(self, owner, plan):
        pass

    def get_subscription(self, owner, plan):
        pass

    def update_payment_method(self, owner, plan):
        pass

    def update_email_address(self, owner, email_address):
        pass

    def update_billing_address(self, owner, name, billing_address):
        pass

    def get_schedule(self, owner):
        pass

    def apply_cancellation_discount(self, owner):
        pass

    def create_setup_intent(self, owner):
        pass


class BillingServiceTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_all_plans_and_tiers()

    def setUp(self):
        self.mock_payment_service = MockPaymentService()
        self.billing_service = BillingService(payment_service=self.mock_payment_service)

    def test_default_payment_service_is_stripe(self):
        requesting_user = OwnerFactory()
        assert isinstance(
            BillingService(requesting_user=requesting_user).payment_service,
            StripeService,
        )

    def test_list_filtered_invoices_calls_payment_service_list_filtered_invoices_with_limit(
        self,
    ):
        owner = OwnerFactory()
        assert self.billing_service.list_filtered_invoices(
            owner
        ) == self.mock_payment_service.list_filtered_invoices(owner)

    @patch("services.tests.test_billing.MockPaymentService.delete_subscription")
    def test_update_plan_to_users_developer_deletes_subscription_if_user_has_stripe_subscription(
        self, delete_subscription_mock
    ):
        owner = OwnerFactory(stripe_subscription_id="tor_dsoe")
        self.billing_service.update_plan(owner, {"value": DEFAULT_FREE_PLAN})
        delete_subscription_mock.assert_called_once_with(owner)

    @patch("shared.plan.service.PlanService.set_default_plan_data")
    @patch("services.tests.test_billing.MockPaymentService.create_checkout_session")
    @patch("services.tests.test_billing.MockPaymentService.modify_subscription")
    @patch("services.tests.test_billing.MockPaymentService.delete_subscription")
    def test_update_plan_to_users_developer_sets_plan_if_no_subscription_id(
        self,
        delete_subscription_mock,
        modify_subscription_mock,
        create_checkout_session_mock,
        set_default_plan_data,
    ):
        owner = OwnerFactory()
        self.billing_service.update_plan(owner, {"value": DEFAULT_FREE_PLAN})

        set_default_plan_data.assert_called_once()

        delete_subscription_mock.assert_not_called()
        modify_subscription_mock.assert_not_called()
        create_checkout_session_mock.assert_not_called()

    @patch("shared.plan.service.PlanService.set_default_plan_data")
    @patch("services.tests.test_billing.MockPaymentService.create_checkout_session")
    @patch("services.tests.test_billing.MockPaymentService.modify_subscription")
    @patch("services.tests.test_billing.MockPaymentService.delete_subscription")
    @patch("services.tests.test_billing.MockPaymentService.get_subscription")
    def test_update_plan_modifies_subscription_if_user_plan_and_subscription_exists(
        self,
        get_subscription_mock,
        delete_subscription_mock,
        modify_subscription_mock,
        create_checkout_session_mock,
        set_default_plan_data,
    ):
        owner = OwnerFactory(stripe_subscription_id=10)
        desired_plan = {"value": PlanName.CODECOV_PRO_YEARLY.value, "quantity": 10}

        get_subscription_mock.return_value = stripe.util.convert_to_stripe_object(
            {
                "schedule": None,
                "current_period_start": 1489799420,
                "current_period_end": 1492477820,
                "quantity": 10,
                "name": PlanName.CODECOV_PRO_YEARLY.value,
                "id": 215,
                "status": "active",
            }
        )

        self.billing_service.update_plan(owner, desired_plan)
        modify_subscription_mock.assert_called_once_with(owner, desired_plan)

        set_default_plan_data.assert_not_called()
        delete_subscription_mock.assert_not_called()
        create_checkout_session_mock.assert_not_called()

    @patch("shared.plan.service.PlanService.set_default_plan_data")
    @patch("services.tests.test_billing.MockPaymentService.create_checkout_session")
    @patch("services.tests.test_billing.MockPaymentService.modify_subscription")
    @patch("services.tests.test_billing.MockPaymentService.delete_subscription")
    def test_update_plan_creates_checkout_session_if_user_plan_and_no_subscription(
        self,
        delete_subscription_mock,
        modify_subscription_mock,
        create_checkout_session_mock,
        set_default_plan_data,
    ):
        owner = OwnerFactory(stripe_subscription_id=None)
        desired_plan = {"value": PlanName.CODECOV_PRO_YEARLY.value, "quantity": 10}
        self.billing_service.update_plan(owner, desired_plan)

        create_checkout_session_mock.assert_called_once_with(owner, desired_plan)

        set_default_plan_data.assert_not_called()
        delete_subscription_mock.assert_not_called()
        modify_subscription_mock.assert_not_called()

    @patch("services.tests.test_billing.MockPaymentService.get_subscription")
    @patch("services.tests.test_billing.MockPaymentService.create_checkout_session")
    @patch("services.tests.test_billing.MockPaymentService.modify_subscription")
    @patch("services.billing.BillingService._cleanup_incomplete_subscription")
    def test_update_plan_cleans_up_incomplete_subscription_and_creates_new_checkout(
        self,
        cleanup_incomplete_mock,
        modify_subscription_mock,
        create_checkout_session_mock,
        get_subscription_mock,
    ):
        owner = OwnerFactory(stripe_subscription_id="sub_123")
        desired_plan = {"value": PlanName.CODECOV_PRO_YEARLY.value, "quantity": 10}

        subscription = stripe.Subscription.construct_from(
            {"status": "incomplete"}, "fake_api_key"
        )
        get_subscription_mock.return_value = subscription

        self.billing_service.update_plan(owner, desired_plan)

        cleanup_incomplete_mock.assert_called_once_with(subscription, owner)
        create_checkout_session_mock.assert_called_once_with(owner, desired_plan)
        modify_subscription_mock.assert_not_called()

    @patch("services.billing.stripe.PaymentIntent.retrieve")
    @patch("services.billing.stripe.Subscription.delete")
    def test_cleanup_incomplete_subscription(self, delete_mock, retrieve_mock):
        owner = OwnerFactory(stripe_subscription_id="sub_123")

        payment_intent = stripe.PaymentIntent.construct_from(
            {"id": "pi_123", "status": "requires_action"}, "fake_api_key"
        )
        subscription = stripe.Subscription.construct_from(
            {"id": "abcd", "latest_invoice": {"payment_intent": "pi_123"}},
            "fake_api_key",
        )
        retrieve_mock.return_value = payment_intent

        self.billing_service._cleanup_incomplete_subscription(subscription, owner)

        retrieve_mock.assert_called_once_with("pi_123")
        delete_mock.assert_called_once_with(subscription)

    @patch("services.billing.stripe.PaymentIntent.retrieve")
    @patch("services.billing.stripe.Subscription.delete")
    def test_cleanup_incomplete_subscription_no_latest_invoice(
        self, delete_mock, retrieve_mock
    ):
        owner = OwnerFactory(stripe_subscription_id="sub_123")

        subscription = stripe.Subscription.construct_from(
            {"id": "sub_123"}, "fake_api_key"
        )

        result = self.billing_service._cleanup_incomplete_subscription(
            subscription, owner
        )

        assert result is None
        delete_mock.assert_not_called()
        retrieve_mock.assert_not_called()
        assert owner.stripe_subscription_id == "sub_123"

    @patch("services.billing.stripe.PaymentIntent.retrieve")
    @patch("services.billing.stripe.Subscription.delete")
    def test_cleanup_incomplete_subscription_no_payment_intent(
        self, delete_mock, retrieve_mock
    ):
        owner = OwnerFactory(stripe_subscription_id="sub_123")

        class MockSubscription:
            id = "sub_123"

            def get(self, key):
                if key == "latest_invoice":
                    return {"payment_intent": None}
                return None

        subscription = MockSubscription()

        result = self.billing_service._cleanup_incomplete_subscription(
            subscription, owner
        )

        assert result is None
        delete_mock.assert_not_called()
        retrieve_mock.assert_not_called()
        assert owner.stripe_subscription_id == "sub_123"

    @patch("services.billing.stripe.PaymentIntent.retrieve")
    @patch("services.billing.stripe.Subscription.delete")
    def test_cleanup_incomplete_subscription_delete_fails(
        self, delete_mock, retrieve_mock
    ):
        owner = OwnerFactory(stripe_subscription_id="sub_123")

        payment_intent = stripe.PaymentIntent.construct_from(
            {"id": "pi_123", "status": "requires_action"}, "fake_api_key"
        )
        subscription = stripe.Subscription.construct_from(
            {"id": "abcd", "latest_invoice": {"payment_intent": "pi_123"}},
            "fake_api_key",
        )
        retrieve_mock.return_value = payment_intent
        delete_mock.side_effect = Exception("Delete failed")

        result = self.billing_service._cleanup_incomplete_subscription(
            subscription, owner
        )

        assert result is None
        retrieve_mock.assert_called_once_with("pi_123")
        delete_mock.assert_called_once_with(subscription)
        assert owner.stripe_subscription_id == "sub_123"

    @patch("shared.plan.service.PlanService.set_default_plan_data")
    @patch("services.tests.test_billing.MockPaymentService.create_checkout_session")
    @patch("services.tests.test_billing.MockPaymentService.modify_subscription")
    @patch("services.tests.test_billing.MockPaymentService.delete_subscription")
    def test_update_plan_does_nothing_if_not_switching_to_user_plan(
        self,
        delete_subscription_mock,
        modify_subscription_mock,
        create_checkout_session_mock,
        set_default_plan_data,
    ):
        owner = OwnerFactory()
        desired_plan = {"value": "v4-50m"}
        self.billing_service.update_plan(owner, desired_plan)

        set_default_plan_data.assert_not_called()
        delete_subscription_mock.assert_not_called()
        modify_subscription_mock.assert_not_called()
        create_checkout_session_mock.assert_not_called()

    @patch("services.tests.test_billing.MockPaymentService.create_checkout_session")
    @patch("services.tests.test_billing.MockPaymentService.modify_subscription")
    def test_update_plan_sentry_user_sentrym(
        self, modify_subscription_mock, create_checkout_session_mock
    ):
        owner = OwnerFactory(sentry_user_id="sentry-user")
        desired_plan = {"value": PlanName.SENTRY_MONTHLY.value}
        self.billing_service.update_plan(owner, desired_plan)

        modify_subscription_mock.assert_not_called()
        create_checkout_session_mock.assert_called_once_with(owner, desired_plan)

    @patch("services.tests.test_billing.MockPaymentService.create_checkout_session")
    @patch("services.tests.test_billing.MockPaymentService.modify_subscription")
    def test_update_plan_sentry_user_sentryy(
        self, modify_subscription_mock, create_checkout_session_mock
    ):
        owner = OwnerFactory(sentry_user_id="sentry-user")
        desired_plan = {"value": PlanName.SENTRY_YEARLY.value}
        self.billing_service.update_plan(owner, desired_plan)

        modify_subscription_mock.assert_not_called()
        create_checkout_session_mock.assert_called_once_with(owner, desired_plan)

    @patch("services.tests.test_billing.MockPaymentService.get_subscription")
    def test_get_subscription(self, get_subscription_mock):
        owner = OwnerFactory()
        self.billing_service.get_subscription(owner)
        get_subscription_mock.assert_called_once_with(owner)

    @patch("services.tests.test_billing.MockPaymentService.update_payment_method")
    def test_update_payment_method(self, get_subscription_mock):
        owner = OwnerFactory()
        self.billing_service.update_payment_method(owner, "abc")
        get_subscription_mock.assert_called_once_with(owner, "abc")

    @patch("services.tests.test_billing.MockPaymentService.update_email_address")
    def test_email_address(self, get_subscription_mock):
        owner = OwnerFactory()
        self.billing_service.update_email_address(owner, "test@gmail.com", False)
        get_subscription_mock.assert_called_once_with(owner, "test@gmail.com", False)

    @patch("services.tests.test_billing.MockPaymentService.get_invoice")
    def test_get_invoice(self, get_invoice_mock):
        owner = OwnerFactory()
        self.billing_service.get_invoice(owner, "abc")
        get_invoice_mock.assert_called_once_with(owner, "abc")
