import json
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import TestCase
from stripe import InvalidRequestError

from codecov_auth.models import Service
from codecov_auth.tests.factories import OwnerFactory
from plan.constants import PlanName
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
                    "description": "(10) users-inappm",
                    "discountable": True,
                    "livemode": False,
                    "metadata": {},
                    "period": {"end": 1521326190, "start": 1518906990},
                    "plan": {
                        "id": "ivory-freelance-040",
                        "name": "users-inappm",
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
        "payment_intent": None,
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


class MockSubscription(object):
    def __init__(self, subscription_params):
        self.schedule = subscription_params["schedule_id"]
        self.current_period_start = subscription_params["start_date"]
        self.current_period_end = subscription_params["end_date"]
        self.items = {
            "data": [
                {
                    "quantity": subscription_params["quantity"],
                    "id": subscription_params["id"],
                    "plan": {"id": subscription_params["name"]},
                }
            ]
        }

    def __getitem__(self, key):
        return getattr(self, key)


class StripeServiceTests(TestCase):
    def setUp(self):
        self.user = OwnerFactory()
        self.stripe = StripeService(requesting_user=self.user)

    def test_stripe_service_requires_requesting_user_to_be_owner_instance(self):
        with self.assertRaises(Exception):
            StripeService(None)

    def _assert_subscription_modify(
        self, subscription_modify_mock, owner, subscription_params, desired_plan
    ):
        subscription_modify_mock.assert_called_once_with(
            owner.stripe_subscription_id,
            cancel_at_period_end=False,
            items=[
                {
                    "id": subscription_params["id"],
                    "plan": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
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
        )

    def _assert_schedule_modify(
        self,
        schedule_modify_mock,
        owner,
        subscription_params,
        desired_plan,
        schedule_id,
    ):
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
                            "plan": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                            "price": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
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

    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.Subscription.modify")
    def test_delete_subscription_without_schedule_modifies_subscription_to_delete_at_end_of_billing_cycle_if_valid_plan(
        self, modify_mock, retrieve_subscription_mock
    ):
        plan = PlanName.CODECOV_PRO_YEARLY.value
        stripe_subscription_id = "sub_1K77Y5GlVGuVgOrkJrLjRnne"
        stripe_schedule_id = None
        owner = OwnerFactory(
            stripe_subscription_id=stripe_subscription_id,
            plan=plan,
            plan_activated_users=[4, 6, 3],
            plan_user_count=9,
        )
        subscription_params = {
            "schedule_id": stripe_schedule_id,
            "start_date": 1639628096,
            "end_date": 1644107871,
            "quantity": 10,
            "name": plan,
            "id": 215,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)
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

    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.Subscription.retrieve")
    @patch("services.billing.stripe.SubscriptionSchedule.release")
    def test_delete_subscription_with_schedule_releases_schedule_and_cancels_subscription_at_end_of_billing_cycle_if_valid_plan(
        self, schedule_release_mock, retrieve_subscription_mock, modify_mock
    ):
        plan = PlanName.CODECOV_PRO_YEARLY.value
        stripe_subscription_id = "sub_1K77Y5GlVGuVgOrkJrLjRnne"
        stripe_schedule_id = "sub_sched_sch1K77Y5GlVGuVgOrkJrLjRnne"
        owner = OwnerFactory(
            stripe_subscription_id=stripe_subscription_id,
            plan=plan,
            plan_activated_users=[4, 6, 3],
            plan_user_count=9,
        )
        subscription_params = {
            "schedule_id": stripe_schedule_id,
            "start_date": 1639628096,
            "end_date": 1644107871,
            "quantity": 10,
            "name": plan,
            "id": 215,
        }

        retrieve_subscription_mock.return_value = MockSubscription(subscription_params)
        self.stripe.delete_subscription(owner)
        schedule_release_mock.assert_called_once_with(stripe_schedule_id)
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
            "name": original_plan,
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
        desired_plan = {"value": PlanName.CODECOV_PRO_YEARLY.value, "quantity": 14}
        assert (
            self.stripe._get_proration_params(owner, desired_plan) == "always_invoice"
        )

        # Test same plan, decrease users
        owner = OwnerFactory(plan=PlanName.CODECOV_PRO_YEARLY.value, plan_user_count=20)
        desired_plan = {"value": PlanName.CODECOV_PRO_YEARLY.value, "quantity": 14}
        assert self.stripe._get_proration_params(owner, desired_plan) == "none"

        # Test going from monthly to yearly
        owner = OwnerFactory(
            plan=PlanName.CODECOV_PRO_MONTHLY.value, plan_user_count=20
        )
        desired_plan = {"value": PlanName.CODECOV_PRO_YEARLY.value, "quantity": 14}
        assert (
            self.stripe._get_proration_params(owner, desired_plan) == "always_invoice"
        )

        # monthly to Sentry monthly plan
        owner = OwnerFactory(
            plan=PlanName.CODECOV_PRO_MONTHLY.value, plan_user_count=20
        )
        desired_plan = {"value": PlanName.SENTRY_MONTHLY.value, "quantity": 19}
        self.stripe._get_proration_params(owner, desired_plan) == "none"
        desired_plan = {"value": PlanName.SENTRY_MONTHLY.value, "quantity": 20}
        self.stripe._get_proration_params(owner, desired_plan) == "always_invoice"
        desired_plan = {"value": PlanName.SENTRY_MONTHLY.value, "quantity": 21}
        assert (
            self.stripe._get_proration_params(owner, desired_plan) == "always_invoice"
        )

        # yearly to Sentry monthly plan
        owner = OwnerFactory(plan=PlanName.CODECOV_PRO_YEARLY.value, plan_user_count=20)
        desired_plan = {"value": PlanName.SENTRY_MONTHLY.value, "quantity": 19}
        assert self.stripe._get_proration_params(owner, desired_plan) == "none"
        desired_plan = {"value": PlanName.SENTRY_MONTHLY.value, "quantity": 20}
        assert self.stripe._get_proration_params(owner, desired_plan) == "none"
        desired_plan = {"value": PlanName.SENTRY_MONTHLY.value, "quantity": 21}
        assert (
            self.stripe._get_proration_params(owner, desired_plan) == "always_invoice"
        )

        # monthly to Sentry monthly plan
        owner = OwnerFactory(
            plan=PlanName.CODECOV_PRO_MONTHLY.value, plan_user_count=20
        )
        desired_plan = {"value": PlanName.SENTRY_MONTHLY.value, "quantity": 19}
        assert self.stripe._get_proration_params(owner, desired_plan) == "none"
        desired_plan = {"value": PlanName.SENTRY_MONTHLY.value, "quantity": 20}
        assert (
            self.stripe._get_proration_params(owner, desired_plan) == "always_invoice"
        )
        desired_plan = {"value": PlanName.SENTRY_MONTHLY.value, "quantity": 21}
        assert (
            self.stripe._get_proration_params(owner, desired_plan) == "always_invoice"
        )

        # yearly to Sentry yearly plan
        owner = OwnerFactory(plan=PlanName.CODECOV_PRO_YEARLY.value, plan_user_count=20)
        desired_plan = {"value": PlanName.SENTRY_YEARLY.value, "quantity": 19}
        assert self.stripe._get_proration_params(owner, desired_plan) == "none"
        desired_plan = {"value": PlanName.SENTRY_YEARLY.value, "quantity": 20}
        assert (
            self.stripe._get_proration_params(owner, desired_plan) == "always_invoice"
        )
        desired_plan = {"value": PlanName.SENTRY_YEARLY.value, "quantity": 21}
        assert (
            self.stripe._get_proration_params(owner, desired_plan) == "always_invoice"
        )

        # monthly to Sentry yearly plan
        owner = OwnerFactory(
            plan=PlanName.CODECOV_PRO_MONTHLY.value, plan_user_count=20
        )
        desired_plan = {"value": PlanName.SENTRY_YEARLY.value, "quantity": 19}
        assert (
            self.stripe._get_proration_params(owner, desired_plan) == "always_invoice"
        )
        desired_plan = {"value": PlanName.SENTRY_YEARLY.value, "quantity": 20}
        assert (
            self.stripe._get_proration_params(owner, desired_plan) == "always_invoice"
        )
        desired_plan = {"value": PlanName.SENTRY_YEARLY.value, "quantity": 21}
        assert (
            self.stripe._get_proration_params(owner, desired_plan) == "always_invoice"
        )

        # Team to Sentry
        owner = OwnerFactory(plan=PlanName.TEAM_MONTHLY.value, plan_user_count=10)
        desired_plan = {"value": PlanName.SENTRY_MONTHLY.value, "quantity": 10}
        assert (
            self.stripe._get_proration_params(owner, desired_plan) == "always_invoice"
        )

        # Team to Pro
        owner = OwnerFactory(plan=PlanName.TEAM_MONTHLY.value, plan_user_count=10)
        desired_plan = {"value": PlanName.CODECOV_PRO_MONTHLY.value, "quantity": 10}
        assert (
            self.stripe._get_proration_params(owner, desired_plan) == "always_invoice"
        )

        # Sentry to Team
        owner = OwnerFactory(plan=PlanName.SENTRY_MONTHLY.value, plan_user_count=10)
        desired_plan = {"value": PlanName.TEAM_MONTHLY.value, "quantity": 10}
        assert self.stripe._get_proration_params(owner, desired_plan) == "none"

        # Sentry to Pro
        owner = OwnerFactory(
            plan=PlanName.CODECOV_PRO_MONTHLY.value, plan_user_count=10
        )
        desired_plan = {"value": PlanName.TEAM_MONTHLY.value, "quantity": 10}
        assert self.stripe._get_proration_params(owner, desired_plan) == "none"

    @patch("services.billing.stripe.checkout.Session.create")
    def test_create_checkout_session_with_email_and_no_stripe_customer_id(
        self, create_checkout_session_mock
    ):
        email = "test-email@gmail.com"
        stripe_customer_id = None
        owner = OwnerFactory(
            service=Service.GITHUB.value,
            email=email,
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

        create_checkout_session_mock.assert_called_once_with(
            billing_address_collection="required",
            payment_method_types=["card"],
            payment_method_collection="if_required",
            client_reference_id=str(owner.ownerid),
            customer_email=owner.email,
            customer=None,
            success_url=f"{settings.CODECOV_DASHBOARD_URL}/plan/gh/{owner.username}?success",
            cancel_url=f"{settings.CODECOV_DASHBOARD_URL}/plan/gh/{owner.username}?cancel",
            mode="subscription",
            line_items=[
                {
                    "price": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
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
        )

    @patch("services.billing.stripe.checkout.Session.create")
    def test_create_checkout_session_with_no_email_and_no_stripe_customer_id(
        self, create_checkout_session_mock
    ):
        email = None
        stripe_customer_id = None
        owner = OwnerFactory(
            service=Service.GITHUB.value,
            email=email,
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

        create_checkout_session_mock.assert_called_once_with(
            billing_address_collection="required",
            payment_method_types=["card"],
            payment_method_collection="if_required",
            client_reference_id=str(owner.ownerid),
            customer_email=owner.email,
            customer=None,
            success_url=f"{settings.CODECOV_DASHBOARD_URL}/plan/gh/{owner.username}?success",
            cancel_url=f"{settings.CODECOV_DASHBOARD_URL}/plan/gh/{owner.username}?cancel",
            mode="subscription",
            line_items=[
                {
                    "price": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
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
        )

    @patch("services.billing.stripe.checkout.Session.create")
    def test_create_checkout_session_with_stripe_customer_id_and_no_email(
        self, create_checkout_session_mock
    ):
        email = None
        stripe_customer_id = "test-cusa78723hb4@"
        owner = OwnerFactory(
            service=Service.GITHUB.value,
            email=email,
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

        create_checkout_session_mock.assert_called_once_with(
            billing_address_collection="required",
            payment_method_types=["card"],
            payment_method_collection="if_required",
            client_reference_id=str(owner.ownerid),
            customer=owner.stripe_customer_id,
            customer_email=None,
            success_url=f"{settings.CODECOV_DASHBOARD_URL}/plan/gh/{owner.username}?success",
            cancel_url=f"{settings.CODECOV_DASHBOARD_URL}/plan/gh/{owner.username}?cancel",
            mode="subscription",
            line_items=[
                {
                    "price": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
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
        )

    @patch("services.billing.stripe.checkout.Session.create")
    def test_create_checkout_session_with_stripe_customer_id_and_email(
        self, create_checkout_session_mock
    ):
        email = "test-email@gmail.com"
        stripe_customer_id = "test-cusa78723hb4@"
        owner = OwnerFactory(
            service=Service.GITHUB.value,
            email=email,
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

        create_checkout_session_mock.assert_called_once_with(
            billing_address_collection="required",
            payment_method_types=["card"],
            payment_method_collection="if_required",
            client_reference_id=str(owner.ownerid),
            customer=owner.stripe_customer_id,
            customer_email=None,
            success_url=f"{settings.CODECOV_DASHBOARD_URL}/plan/gh/{owner.username}?success",
            cancel_url=f"{settings.CODECOV_DASHBOARD_URL}/plan/gh/{owner.username}?cancel",
            mode="subscription",
            line_items=[
                {
                    "price": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
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
        )

    def test_get_subscription_when_no_subscription(self):
        owner = OwnerFactory(stripe_subscription_id=None)
        assert self.stripe.get_subscription(owner) == None

    @patch("services.billing.stripe.Subscription.retrieve")
    def test_get_subscription_returns_stripe_data(self, subscription_retrieve_mock):
        owner = OwnerFactory(stripe_subscription_id="abc")
        # only including fields relevant to implementation
        stripe_data_subscription = {"doesnt": "matter"}
        payment_method_id = "pm_something_something"
        subscription_retrieve_mock.return_value = stripe_data_subscription
        assert self.stripe.get_subscription(owner) == stripe_data_subscription
        subscription_retrieve_mock.assert_called_once_with(
            owner.stripe_subscription_id,
            expand=[
                "latest_invoice",
                "customer",
                "customer.invoice_settings.default_payment_method",
            ],
        )

    def test_update_payment_method_when_no_subscription(self):
        owner = OwnerFactory(stripe_subscription_id=None)
        assert self.stripe.update_payment_method(owner, "abc") == None

    @patch("services.billing.stripe.PaymentMethod.attach")
    @patch("services.billing.stripe.Customer.modify")
    def test_update_payment_method(self, modify_customer_mock, attach_payment_mock):
        payment_method_id = "pm_1234567"
        subscription_id = "sub_abc"
        customer_id = "cus_abc"
        owner = OwnerFactory(
            stripe_subscription_id=subscription_id, stripe_customer_id=customer_id
        )
        self.stripe.update_payment_method(owner, payment_method_id)
        attach_payment_mock.assert_called_once_with(
            payment_method_id, customer=customer_id
        )
        modify_customer_mock.assert_called_once_with(
            customer_id, invoice_settings={"default_payment_method": payment_method_id}
        )

    def test_update_email_address_with_invalid_email(self):
        owner = OwnerFactory(stripe_subscription_id=None)
        assert self.stripe.update_email_address(owner, "not-an-email") == None

    def test_update_email_address_when_no_subscription(self):
        owner = OwnerFactory(stripe_subscription_id=None)
        assert self.stripe.update_email_address(owner, "test@gmail.com") == None

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

    @patch("services.billing.stripe.Invoice.retrieve")
    def test_get_invoice_not_found(self, retrieve_invoice_mock):
        invoice_id = "abc"
        retrieve_invoice_mock.side_effect = InvalidRequestError(
            message="not found", param=invoice_id
        )
        assert self.stripe.get_invoice(OwnerFactory(), invoice_id) == None
        retrieve_invoice_mock.assert_called_once_with(invoice_id)

    @patch("services.billing.stripe.Invoice.retrieve")
    def test_get_invoice_customer_dont_match(self, retrieve_invoice_mock):
        owner = OwnerFactory(stripe_customer_id="something_very_very_random_cus_abc")
        invoice_id = "abc"
        invoice = {"invoice_id": "abc", "customer": "cus_abc"}
        retrieve_invoice_mock.return_value = invoice
        assert self.stripe.get_invoice(owner, invoice_id) == None
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
            plan="users-inappm",
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
        assert owner.stripe_coupon_id == None

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
        assert owner.stripe_coupon_id == None

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

    def get_schedule(self, owner):
        pass

    def apply_cancellation_discount(self, owner):
        pass


class BillingServiceTests(TestCase):
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
    def test_update_plan_to_users_basic_deletes_subscription_if_user_has_stripe_subscription(
        self, delete_subscription_mock
    ):
        owner = OwnerFactory(stripe_subscription_id="tor_dsoe")
        self.billing_service.update_plan(
            owner, {"value": PlanName.BASIC_PLAN_NAME.value}
        )
        delete_subscription_mock.assert_called_once_with(owner)

    @patch("plan.service.PlanService.set_default_plan_data")
    @patch("services.tests.test_billing.MockPaymentService.create_checkout_session")
    @patch("services.tests.test_billing.MockPaymentService.modify_subscription")
    @patch("services.tests.test_billing.MockPaymentService.delete_subscription")
    def test_update_plan_to_users_basic_sets_plan_if_no_subscription_id(
        self,
        delete_subscription_mock,
        modify_subscription_mock,
        create_checkout_session_mock,
        set_default_plan_data,
    ):
        owner = OwnerFactory()
        self.billing_service.update_plan(
            owner, {"value": PlanName.BASIC_PLAN_NAME.value}
        )

        set_default_plan_data.assert_called_once()

        delete_subscription_mock.assert_not_called()
        modify_subscription_mock.assert_not_called()
        create_checkout_session_mock.assert_not_called()

    @patch("plan.service.PlanService.set_default_plan_data")
    @patch("services.tests.test_billing.MockPaymentService.create_checkout_session")
    @patch("services.tests.test_billing.MockPaymentService.modify_subscription")
    @patch("services.tests.test_billing.MockPaymentService.delete_subscription")
    def test_update_plan_modifies_subscription_if_user_plan_and_subscription_exists(
        self,
        delete_subscription_mock,
        modify_subscription_mock,
        create_checkout_session_mock,
        set_default_plan_data,
    ):
        owner = OwnerFactory(stripe_subscription_id=10)
        desired_plan = {"value": PlanName.CODECOV_PRO_YEARLY.value, "quantity": 10}
        self.billing_service.update_plan(owner, desired_plan)

        modify_subscription_mock.assert_called_once_with(owner, desired_plan)

        set_default_plan_data.assert_not_called()
        delete_subscription_mock.assert_not_called()
        create_checkout_session_mock.assert_not_called()

    @patch("plan.service.PlanService.set_default_plan_data")
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

    @patch("plan.service.PlanService.set_default_plan_data")
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
        self.billing_service.update_email_address(owner, "test@gmail.com")
        get_subscription_mock.assert_called_once_with(owner, "test@gmail.com")

    @patch("services.tests.test_billing.MockPaymentService.get_invoice")
    def test_get_invoice(self, get_invoice_mock):
        owner = OwnerFactory()
        self.billing_service.get_invoice(owner, "abc")
        get_invoice_mock.assert_called_once_with(owner, "abc")
