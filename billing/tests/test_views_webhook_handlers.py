import json
import time
from datetime import datetime
from unittest.mock import Mock, call, patch

import stripe
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIRequestFactory

from billing.constants import DEFAULT_FREE_PLAN, PlanName
from billing.models import Plan
from billing.views import StripeHTTPHeaders, StripeWebhookHandler
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from services.task import TaskService


class MockPaymentIntent:
    def __init__(self, noCard=False):
        self.status = "succeeded"
        self.id = "pi_123"
        self.next_action = None
        if noCard:
            self.payment_method = None
        else:
            self.payment_method = {
                "card": {
                    "brand": "visa",
                    "last4": "1234"
                }
            }


class MockSubscription:
    def __init__(self, owner, params):
        self.plan = Mock()
        self.plan.id = params["new_plan"]
        self.customer = owner.stripe_customer_id
        self.id = params["subscription_id"]
        self.quantity = params["new_quantity"]


class StripeWebhookHandlerTests(TestCase):
    def setUp(self):
        self.owner = OwnerFactory(
            email="owner@example.com",
            username="owner",
            plan=PlanName.CODECOV_PRO_MONTHLY.value,
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
        )
        self.handler = StripeWebhookHandler()

    def _send_event(self, payload, errorSig=None):
        timestamp = time.time_ns()

        request = APIRequestFactory().post(
            reverse("stripe-webhook"), data=payload, format="json"
        )

        return self.client.post(
            reverse("stripe-webhook"),
            **{
                StripeHTTPHeaders.SIGNATURE: errorSig
                or "t={},v1={}".format(
                    timestamp,
                    stripe.WebhookSignature._compute_signature(
                        "{}.{}".format(timestamp, request.body.decode("utf-8")),
                        settings.STRIPE_ENDPOINT_SECRET,
                    ),
                )
            },
            data=payload,
            format="json",
        )

    def add_second_owner(self):
        self.other_owner = OwnerFactory(
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
        )

    @patch("services.task.TaskService.send_email")
    def test_invoice_payment_succeeded_emails_delinquents(self, mocked_send_email):
        non_admin = OwnerFactory(email="non-admin@codecov.io")
        admin_1 = OwnerFactory(email="admin1@codecov.io")
        admin_2 = OwnerFactory(email="admin2@codecov.io")
        self.owner.admins = [admin_1.ownerid, admin_2.ownerid]
        self.owner.plan_activated_users = [non_admin.ownerid]
        self.owner.email = "owner@codecov.io"
        self.owner.delinquent = True
        self.owner.save()
        self.add_second_owner()
        self.other_owner.delinquent = False
        self.other_owner.save()

        response = self._send_event(
            payload={
                "type": "invoice.payment_succeeded",
                "data": {
                    "object": {
                        "customer": self.owner.stripe_customer_id,
                        "subscription": self.owner.stripe_subscription_id,
                        "total": 24000,
                        "hosted_invoice_url": "https://stripe.com",
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        self.other_owner.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(self.owner.delinquent)
        self.assertFalse(self.other_owner.delinquent)

        expected_calls = [
            call(
                to_addr=self.owner.email,
                subject="You're all set",
                template_name="success-after-failed-payment",
                amount=240,
                cta_link="https://stripe.com",
                date=datetime.now().strftime("%B %-d, %Y"),
            ),
            call(
                to_addr=admin_1.email,
                subject="You're all set",
                template_name="success-after-failed-payment",
                amount=240,
                cta_link="https://stripe.com",
                date=datetime.now().strftime("%B %-d, %Y"),
            ),
            call(
                to_addr=admin_2.email,
                subject="You're all set",
                template_name="success-after-failed-payment",
                amount=240,
                cta_link="https://stripe.com",
                date=datetime.now().strftime("%B %-d, %Y"),
            ),
        ]

        mocked_send_email.assert_has_calls(expected_calls)

    @patch("services.billing.stripe.PaymentIntent.retrieve")
    def test_invoice_payment_failed_sets_owner_delinquent(self, retrieve_paymentintent_mock):
        self.owner.delinquent = False
        self.owner.save()

        retrieve_paymentintent_mock.return_value = stripe.PaymentIntent.construct_from(
            {
                "status": "requires_action",
                "next_action": {"type": "verify_with_microdeposits"},
            },
            "payment_intent_asdf",
        )

        response = self._send_event(
            payload={
                "type": "invoice.payment_failed",
                "data": {
                    "object": {
                        "customer": self.owner.stripe_customer_id,
                        "subscription": self.owner.stripe_subscription_id,
                        "total": 24000,
                        "hosted_invoice_url": "https://stripe.com",
                        "payment_intent": "payment_intent_asdf",
                        "default_payment_method": {},
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(self.owner.delinquent)

    @patch("services.task.TaskService.send_email")
    @patch("services.billing.stripe.PaymentIntent.retrieve")
    def test_invoice_payment_failed_sends_email_to_admins(
        self,
        retrieve_paymentintent_mock,
        mocked_send_email,
    ):
        non_admin = OwnerFactory(email="non-admin@codecov.io")
        admin_1 = OwnerFactory(email="admin1@codecov.io")
        admin_2 = OwnerFactory(email="admin2@codecov.io")
        self.owner.admins = [admin_1.ownerid, admin_2.ownerid]
        self.owner.plan_activated_users = [non_admin.ownerid]
        self.owner.email = "owner@codecov.io"
        self.owner.save()

        retrieve_paymentintent_mock.return_value = MockPaymentIntent()

        response = self._send_event(
            payload={
                "type": "invoice.payment_failed",
                "data": {
                    "object": {
                        "customer": self.owner.stripe_customer_id,
                        "subscription": self.owner.stripe_subscription_id,
                        "total": 24000,
                        "hosted_invoice_url": "https://stripe.com",
                        "payment_intent": "payment_intent_asdf",
                        "default_payment_method": {},
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(self.owner.delinquent)

        expected_calls = [
            call(
                to_addr=self.owner.email,
                subject="Your Codecov payment failed",
                template_name="failed-payment",
                name=self.owner.username,
                amount=240,
                card_type="visa",
                last_four="1234",
                cta_link="https://stripe.com",
                date=datetime.now().strftime("%B %-d, %Y"),
            ),
            call(
                to_addr=admin_1.email,
                subject="Your Codecov payment failed",
                template_name="failed-payment",
                name=admin_1.username,
                amount=240,
                card_type="visa",
                last_four="1234",
                cta_link="https://stripe.com",
                date=datetime.now().strftime("%B %-d, %Y"),
            ),
            call(
                to_addr=admin_2.email,
                subject="Your Codecov payment failed",
                template_name="failed-payment",
                name=admin_2.username,
                amount=240,
                card_type="visa",
                last_four="1234",
                cta_link="https://stripe.com",
                date=datetime.now().strftime("%B %-d, %Y"),
            ),
        ]

        mocked_send_email.assert_has_calls(expected_calls)

    def test_customer_subscription_deleted_sets_plan_to_free(self):
        self.owner.plan = PlanName.CODECOV_PRO_YEARLY.value
        self.owner.plan_user_count = 20
        self.owner.save()

        self._send_event(
            payload={
                "type": "customer.subscription.deleted",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id,
                        "plan": {"name": self.owner.plan},
                        "status": "active",
                    }
                },
            }
        )
        self.owner.refresh_from_db()

        self.assertEqual(self.owner.plan, DEFAULT_FREE_PLAN)
        self.assertEqual(self.owner.plan_user_count, 1)
        self.assertIsNone(self.owner.plan_activated_users)
        self.assertIsNone(self.owner.stripe_subscription_id)

    def test_customer_subscription_deleted_deactivates_all_repos(self):
        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.owner, activated=True, active=True)

        self.assertEqual(
            self.owner.repository_set.filter(activated=True, active=True).count(), 3
        )

        self._send_event(
            payload={
                "type": "customer.subscription.deleted",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id,
                        "plan": {"name": PlanName.CODECOV_PRO_MONTHLY.value},
                        "status": "active",
                    }
                },
            }
        )

        self.assertEqual(
            self.owner.repository_set.filter(activated=False, active=False).count(), 3
        )