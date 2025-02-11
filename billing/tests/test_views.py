import time
from datetime import datetime
from unittest.mock import Mock, call, patch

import stripe
from django.conf import settings
from freezegun import freeze_time
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIRequestFactory, APITestCase
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory
from shared.plan.constants import DEFAULT_FREE_PLAN, PlanName

from billing.helpers import mock_all_plans_and_tiers
from billing.views import StripeWebhookHandler
from codecov_auth.models import Plan

from ..constants import StripeHTTPHeaders


class MockSubscriptionPlan(object):
    def __init__(self, params):
        self.id = params["new_plan"]


class MockSubscription(object):
    def __init__(self, owner, params):
        self.metadata = {"obo_organization": owner.ownerid, "obo": 15}
        self.plan = MockSubscriptionPlan(params)
        self.quantity = params["new_quantity"]
        self.customer = "cus_123"
        self.id = params["subscription_id"]
        self.items = {
            "data": [
                {
                    "quantity": params["new_quantity"],
                    "plan": {"id": params["new_plan"]},
                }
            ]
        }

    def __getitem__(self, key):
        return getattr(self, key)


class MockCard(object):
    def __init__(self):
        self.brand = "visa"
        self.last4 = "1234"

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


class MockPaymentMethod(object):
    def __init__(self, noCard=False):
        if noCard:
            self.card = None
            return

        self.card = MockCard()

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


class MockPaymentIntent(object):
    def __init__(self, noCard=False):
        self.payment_method = MockPaymentMethod(noCard)
        self.status = "succeeded"

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


class StripeWebhookHandlerTests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_all_plans_and_tiers()

    def setUp(self):
        self.owner = OwnerFactory(
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
        )

    # Creates a second owner that shares billing details with self.owner.
    # This is used to test the case where owners are manually set to share a
    # subscription in Stripe.
    def add_second_owner(self):
        self.other_owner = OwnerFactory(
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
        )

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

    def test_invalid_event_signature(self):
        response = self._send_event(
            payload={
                "type": "blah",
                "data": {},
            },
            errorSig="lol",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_invoice_payment_succeeded_sets_owner_delinquent_false(self):
        self.owner.delinquent = True
        self.owner.save()

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
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert self.owner.delinquent is False

    def test_invoice_payment_succeeded_sets_multiple_owners_delinquent_false(self):
        self.add_second_owner()
        self.owner.delinquent = True
        self.owner.save()
        self.other_owner.delinquent = True
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
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert self.owner.delinquent is False
        assert self.other_owner.delinquent is False

    @patch("services.task.TaskService.send_email")
    def test_invoice_payment_succeeded_emails_only_emails_delinquents(
        self,
        mocked_send_email,
    ):
        self.add_second_owner()
        self.owner.delinquent = False
        self.owner.save()

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
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert self.owner.delinquent is False

        mocked_send_email.assert_not_called()

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
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert self.owner.delinquent is False
        assert self.other_owner.delinquent is False

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
    def test_invoice_payment_failed_skips_delinquency_if_payment_intent_requires_action(
        self, retrieve_paymentintent_mock
    ):
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
                        "default_payment_method": None,
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert self.owner.delinquent is False
        retrieve_paymentintent_mock.assert_called_once_with("payment_intent_asdf")

    @patch("services.billing.stripe.PaymentIntent.retrieve")
    def test_invoice_payment_failed_sets_owner_delinquent_true(
        self, retrieve_paymentintent_mock
    ):
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
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert self.owner.delinquent is True

    @patch("services.billing.stripe.PaymentIntent.retrieve")
    def test_invoice_payment_failed_sets_multiple_owners_delinquent_true(
        self, retrieve_paymentintent_mock
    ):
        self.add_second_owner()
        self.owner.delinquent = False
        self.owner.save()
        self.other_owner.delinquent = False
        self.other_owner.save()

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
        self.other_owner.refresh_from_db()
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert self.owner.delinquent is True
        assert self.other_owner.delinquent is True

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
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert self.owner.delinquent is True

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

    @patch("services.task.TaskService.send_email")
    @patch("services.billing.stripe.PaymentIntent.retrieve")
    def test_invoice_payment_failed_sends_email_to_admins_no_card(
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

        retrieve_paymentintent_mock.return_value = MockPaymentIntent(noCard=True)

        response = self._send_event(
            payload={
                "type": "invoice.payment_failed",
                "data": {
                    "object": {
                        "customer": self.owner.stripe_customer_id,
                        "subscription": self.owner.stripe_subscription_id,
                        "default_payment_method": None,
                        "total": 24000,
                        "hosted_invoice_url": "https://stripe.com",
                        "payment_intent": {
                            "id": "payment_intent_asdf",
                            "status": "succeeded",
                        },
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert self.owner.delinquent is True

        expected_calls = [
            call(
                to_addr=self.owner.email,
                subject="Your Codecov payment failed",
                template_name="failed-payment",
                name=self.owner.username,
                amount=240,
                card_type=None,
                last_four=None,
                cta_link="https://stripe.com",
                date=datetime.now().strftime("%B %-d, %Y"),
            ),
            call(
                to_addr=admin_1.email,
                subject="Your Codecov payment failed",
                template_name="failed-payment",
                name=admin_1.username,
                amount=240,
                card_type=None,
                last_four=None,
                cta_link="https://stripe.com",
                date=datetime.now().strftime("%B %-d, %Y"),
            ),
            call(
                to_addr=admin_2.email,
                subject="Your Codecov payment failed",
                template_name="failed-payment",
                name=admin_2.username,
                amount=240,
                card_type=None,
                last_four=None,
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

        assert self.owner.plan == DEFAULT_FREE_PLAN
        assert self.owner.plan_user_count == 1
        assert self.owner.plan_activated_users is None
        assert self.owner.stripe_subscription_id is None

    def test_customer_subscription_deleted_sets_plan_to_free_mutliple_owner(self):
        self.add_second_owner()
        self.owner.plan = PlanName.CODECOV_PRO_YEARLY.value
        self.owner.plan_user_count = 20
        self.owner.save()
        self.other_owner.plan = PlanName.CODECOV_PRO_YEARLY.value
        self.other_owner.plan_user_count = 20
        self.other_owner.save()

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
        self.other_owner.refresh_from_db()

        assert self.owner.plan == DEFAULT_FREE_PLAN
        assert self.owner.plan_user_count == 1
        assert self.owner.plan_activated_users is None
        assert self.owner.stripe_subscription_id is None

        assert self.other_owner.plan == DEFAULT_FREE_PLAN
        assert self.other_owner.plan_user_count == 1
        assert self.other_owner.plan_activated_users is None
        assert self.other_owner.stripe_subscription_id is None

    def test_customer_subscription_deleted_deactivates_all_repos(self):
        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.owner, activated=True, active=True)

        assert (
            self.owner.repository_set.filter(activated=True, active=True).count() == 3
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

        assert (
            self.owner.repository_set.filter(activated=False, active=False).count() == 3
        )

    def test_customer_subscription_deleted_deactivates_all_repos_multiple_owner(self):
        self.add_second_owner()
        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.other_owner, activated=True, active=True)
        RepositoryFactory(author=self.other_owner, activated=True, active=True)
        RepositoryFactory(author=self.other_owner, activated=True, active=True)

        self.owner.refresh_from_db()
        self.other_owner.refresh_from_db()

        assert (
            self.owner.repository_set.filter(activated=True, active=True).count() == 3
        )
        assert (
            self.other_owner.repository_set.filter(activated=True, active=True).count()
            == 3
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

        self.owner.refresh_from_db()
        self.other_owner.refresh_from_db()

        assert (
            self.owner.repository_set.filter(activated=False, active=False).count() == 3
        )
        assert (
            self.other_owner.repository_set.filter(
                activated=False, active=False
            ).count()
            == 3
        )

    @patch("logging.Logger.info")
    def test_customer_subscription_deleted_no_customer(self, log_info_mock):
        self.owner.plan = PlanName.CODECOV_PRO_MONTHLY.value
        self.owner.plan_user_count = 20
        self.owner.save()

        self._send_event(
            payload={
                "type": "customer.subscription.deleted",
                "data": {
                    "object": {
                        "id": "HUH",
                        "customer": "nah",
                        "plan": {"name": self.owner.plan},
                        "status": "active",
                    }
                },
            }
        )

        log_info_mock.assert_called_with(
            "Customer Subscription Deleted - Couldn't find owner, subscription likely already deleted",
            extra={
                "stripe_subscription_id": "HUH",
                "stripe_customer_id": "nah",
            },
        )

    def test_customer_created_logs_and_doesnt_crash(self):
        self._send_event(
            payload={
                "type": "customer.created",
                "data": {"object": {"id": "FOEKDCDEQ", "email": "test@email.com"}},
            }
        )

    @patch("billing.views.StripeWebhookHandler._has_unverified_initial_payment_method")
    def test_customer_subscription_created_early_returns_if_unverified_payment(
        self, mock_has_unverified
    ):
        mock_has_unverified.return_value = True
        self.owner.stripe_subscription_id = None
        self.owner.stripe_customer_id = None
        self.owner.plan = "users-basic"
        self.owner.save()

        response = self._send_event(
            payload={
                "type": "customer.subscription.created",
                "data": {
                    "object": {
                        "id": "sub_123",
                        "customer": "cus_123",
                        "plan": {"id": "plan_pro_yearly"},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": 20,
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert response.status_code == status.HTTP_204_NO_CONTENT
        # Subscription and customer IDs should be set
        assert self.owner.stripe_subscription_id == "sub_123"
        assert self.owner.stripe_customer_id == "cus_123"
        # But plan should not be updated since payment is unverified
        assert self.owner.plan == "users-basic"
        mock_has_unverified.assert_called_once()

    def test_customer_subscription_created_does_nothing_if_no_plan_id(self):
        self.owner.stripe_subscription_id = None
        self.owner.stripe_customer_id = None
        self.owner.save()

        self._send_event(
            payload={
                "type": "customer.subscription.created",
                "data": {
                    "object": {
                        "id": "FOEKDCDEQ",
                        "customer": "sdo050493",
                        "plan": {"id": None},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": 20,
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.stripe_subscription_id is None
        assert self.owner.stripe_customer_id is None

    def test_customer_subscription_created_does_nothing_if_plan_not_paid_user_plan(
        self,
    ):
        self.owner.stripe_subscription_id = None
        self.owner.stripe_customer_id = None
        self.owner.save()

        self._send_event(
            payload={
                "type": "customer.subscription.created",
                "data": {
                    "object": {
                        "id": "FOEKDCDEQ",
                        "customer": "sdo050493",
                        "plan": {"id": "plan_free"},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": 20,
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.stripe_subscription_id is None
        assert self.owner.stripe_customer_id is None

    @patch("billing.views.StripeWebhookHandler._has_unverified_initial_payment_method")
    def test_customer_subscription_created_sets_plan_info(
        self, has_unverified_initial_payment_method_mock
    ):
        has_unverified_initial_payment_method_mock.return_value = False
        self.owner.stripe_subscription_id = None
        self.owner.stripe_customer_id = None
        self.owner.save()

        stripe_subscription_id = "FOEKDCDEQ"
        stripe_customer_id = "sdo050493"
        plan_name = PlanName.CODECOV_PRO_YEARLY.value
        quantity = 20

        self._send_event(
            payload={
                "type": "customer.subscription.created",
                "data": {
                    "object": {
                        "id": stripe_subscription_id,
                        "customer": stripe_customer_id,
                        "plan": {"id": "plan_pro_yearly"},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": quantity,
                        "status": "active",
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.stripe_subscription_id == stripe_subscription_id
        assert self.owner.stripe_customer_id == stripe_customer_id
        assert self.owner.plan_user_count == quantity
        assert self.owner.plan_auto_activate is True
        assert self.owner.plan == plan_name

    @freeze_time("2023-06-19")
    @patch("billing.views.StripeWebhookHandler._has_unverified_initial_payment_method")
    @patch("shared.plan.service.PlanService.expire_trial_when_upgrading")
    @patch("services.billing.stripe.PaymentMethod.attach")
    @patch("services.billing.stripe.Customer.modify")
    def test_customer_subscription_created_can_trigger_trial_expiration(
        self,
        c_mock,
        pm_mock,
        expire_trial_when_upgrading_mock,
        has_unverified_initial_payment_method_mock,
    ):
        has_unverified_initial_payment_method_mock.return_value = False
        stripe_subscription_id = "FOEKDCDEQ"
        stripe_customer_id = "sdo050493"
        quantity = 20

        self._send_event(
            payload={
                "type": "customer.subscription.created",
                "data": {
                    "object": {
                        "id": stripe_subscription_id,
                        "customer": stripe_customer_id,
                        "plan": {"id": "plan_pro_yearly"},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": quantity,
                        "default_payment_method": "blabla",
                    }
                },
            }
        )

        expire_trial_when_upgrading_mock.assert_called_once()

    @patch("billing.views.StripeWebhookHandler._has_unverified_initial_payment_method")
    @patch("services.billing.stripe.PaymentMethod.attach")
    @patch("services.billing.stripe.Customer.modify")
    def test_customer_subscription_updated_does_not_change_subscription_if_not_paid_user_plan(
        self,
        c_mock,
        pm_mock,
        has_unverified_initial_payment_method_mock,
    ):
        has_unverified_initial_payment_method_mock.return_value = False
        self.owner.plan = DEFAULT_FREE_PLAN
        self.owner.plan_user_count = 0
        self.owner.plan_auto_activate = False
        self.owner.save()

        self._send_event(
            payload={
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id,
                        "plan": {"id": "plan_free"},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": 20,
                        "status": "active",
                        "schedule": None,
                        "default_payment_method": "pm_1LhiRsGlVGuVgOrkQguJXdeV",
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.plan == DEFAULT_FREE_PLAN
        assert self.owner.plan_user_count == 0
        assert self.owner.plan_auto_activate == False
        pm_mock.assert_called_once_with(
            "pm_1LhiRsGlVGuVgOrkQguJXdeV", customer=self.owner.stripe_customer_id
        )
        c_mock.assert_called_once_with(
            self.owner.stripe_customer_id,
            invoice_settings={"default_payment_method": "pm_1LhiRsGlVGuVgOrkQguJXdeV"},
        )

    @patch("billing.views.StripeWebhookHandler._has_unverified_initial_payment_method")
    @patch("logging.Logger.info")
    @patch("services.billing.stripe.PaymentMethod.attach")
    @patch("services.billing.stripe.Customer.modify")
    def test_customer_subscription_updated_does_not_change_subscription_if_there_is_a_schedule(
        self,
        c_mock,
        pm_mock,
        log_info_mock,
        has_unverified_initial_payment_method_mock,
    ):
        has_unverified_initial_payment_method_mock.return_value = False
        self.owner.plan = "users-pr-inappy"
        self.owner.plan_user_count = 10
        self.owner.plan_auto_activate = False
        self.owner.save()

        self._send_event(
            payload={
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id,
                        "plan": {"id": "plan_pro_yearly"},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": 20,
                        "status": "active",
                        "schedule": "sub_sched_1K8xfkGlVGuVgOrkxvroyZdH",
                        "default_payment_method": "pm_1LhiRsGlVGuVgOrkQguJXdeV",
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.plan == "users-pr-inappy"
        assert self.owner.plan_user_count == 10
        assert self.owner.plan_auto_activate == False
        pm_mock.assert_called_once_with(
            "pm_1LhiRsGlVGuVgOrkQguJXdeV", customer=self.owner.stripe_customer_id
        )
        c_mock.assert_called_once_with(
            self.owner.stripe_customer_id,
            invoice_settings={"default_payment_method": "pm_1LhiRsGlVGuVgOrkQguJXdeV"},
        )

        log_info_mock.assert_called_once_with(
            "Stripe webhook event received",
            extra={"stripe_webhook_event": "customer.subscription.updated"},
        )

    @patch("billing.views.StripeWebhookHandler._has_unverified_initial_payment_method")
    @patch("services.billing.stripe.PaymentMethod.attach")
    @patch("services.billing.stripe.Customer.modify")
    def test_customer_subscription_updated_sets_free_and_deactivates_all_repos_if_incomplete_expired(
        self,
        c_mock,
        pm_mock,
        has_unverified_initial_payment_method_mock,
    ):
        has_unverified_initial_payment_method_mock.return_value = False
        self.owner.plan = "users-pr-inappy"
        self.owner.plan_user_count = 10
        self.owner.plan_auto_activate = False
        self.owner.save()

        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.owner, activated=True, active=True)
        assert self.owner.repository_set.count() == 3

        self._send_event(
            payload={
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id,
                        "plan": {
                            "id": "plan_pro_yearly",
                        },
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": 20,
                        "status": "incomplete_expired",
                        "schedule": None,
                        "default_payment_method": "pm_1LhiRsGlVGuVgOrkQguJXdeV",
                    }
                },
            }
        )
        self.owner.refresh_from_db()

        assert self.owner.plan == DEFAULT_FREE_PLAN
        assert self.owner.plan_user_count == 1
        assert self.owner.plan_auto_activate == False
        assert self.owner.stripe_subscription_id is None
        assert (
            self.owner.repository_set.filter(active=True, activated=True).count() == 0
        )
        pm_mock.assert_called_once_with(
            "pm_1LhiRsGlVGuVgOrkQguJXdeV", customer=self.owner.stripe_customer_id
        )
        c_mock.assert_called_once_with(
            self.owner.stripe_customer_id,
            invoice_settings={"default_payment_method": "pm_1LhiRsGlVGuVgOrkQguJXdeV"},
        )

    @patch("billing.views.StripeWebhookHandler._has_unverified_initial_payment_method")
    def test_customer_subscription_updated_payment_failed(
        self, has_unverified_initial_payment_method_mock
    ):
        has_unverified_initial_payment_method_mock.return_value = False
        self.owner.delinquent = False
        self.owner.save()

        self._send_event(
            payload={
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id,
                        "plan": {"id": "?"},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": 20,
                        "status": "active",
                        "schedule": None,
                        "default_payment_method": "pm_1LhiRsGlVGuVgOrkQguJXdeV",
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
                },
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.delinquent == True

    @patch("billing.views.StripeWebhookHandler._has_unverified_initial_payment_method")
    @patch("services.billing.stripe.PaymentMethod.attach")
    @patch("services.billing.stripe.Customer.modify")
    def test_customer_subscription_updated_sets_free_and_deactivates_all_repos_if_incomplete_expired_multiple_owner(
        self,
        c_mock,
        pm_mock,
        has_unverified_initial_payment_method_mock,
    ):
        has_unverified_initial_payment_method_mock.return_value = False
        self.add_second_owner()
        self.owner.plan = "users-pr-inappy"
        self.owner.plan_user_count = 10
        self.owner.plan_auto_activate = False
        self.owner.save()
        self.other_owner.plan = "users-pr-inappy"
        self.other_owner.plan_user_count = 10
        self.other_owner.plan_auto_activate = False
        self.other_owner.save()

        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.other_owner, activated=True, active=True)
        RepositoryFactory(author=self.other_owner, activated=True, active=True)
        RepositoryFactory(author=self.other_owner, activated=True, active=True)
        assert self.owner.repository_set.count() == 3
        assert self.other_owner.repository_set.count() == 3

        self._send_event(
            payload={
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id,
                        "plan": {
                            "id": "plan_pro_yearly",
                        },
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": 20,
                        "status": "incomplete_expired",
                        "schedule": None,
                        "default_payment_method": "pm_1LhiRsGlVGuVgOrkQguJXdeV",
                    }
                },
            }
        )
        self.owner.refresh_from_db()
        self.other_owner.refresh_from_db()

        assert self.owner.plan == DEFAULT_FREE_PLAN
        assert self.owner.plan_user_count == 1
        assert self.owner.plan_auto_activate == False
        assert self.owner.stripe_subscription_id is None
        assert (
            self.owner.repository_set.filter(active=True, activated=True).count() == 0
        )
        assert self.other_owner.plan == DEFAULT_FREE_PLAN
        assert self.other_owner.plan_user_count == 1
        assert self.other_owner.plan_auto_activate == False
        assert self.other_owner.stripe_subscription_id is None
        assert (
            self.other_owner.repository_set.filter(active=True, activated=True).count()
            == 0
        )
        pm_mock.assert_called_once_with(
            "pm_1LhiRsGlVGuVgOrkQguJXdeV", customer=self.owner.stripe_customer_id
        )
        c_mock.assert_called_once_with(
            self.owner.stripe_customer_id,
            invoice_settings={"default_payment_method": "pm_1LhiRsGlVGuVgOrkQguJXdeV"},
        )

    @patch("billing.views.StripeWebhookHandler._has_unverified_initial_payment_method")
    @patch("services.billing.stripe.PaymentMethod.attach")
    @patch("services.billing.stripe.Customer.modify")
    def test_customer_subscription_updated_sets_fields_on_success(
        self,
        c_mock,
        pm_mock,
        has_unverified_initial_payment_method_mock,
    ):
        has_unverified_initial_payment_method_mock.return_value = False
        self.owner.plan = "users-free"
        self.owner.plan_user_count = 5
        self.owner.plan_auto_activate = False

        plan_name = "users-pr-inappy"
        quantity = 20

        self._send_event(
            payload={
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id,
                        "plan": {"id": "plan_pro_yearly"},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": quantity,
                        "status": "active",
                        "schedule": None,
                        "default_payment_method": "pm_1LhiRsGlVGuVgOrkQguJXdeV",
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.plan == plan_name
        assert self.owner.plan_user_count == quantity
        assert self.owner.plan_auto_activate == True
        pm_mock.assert_called_once_with(
            "pm_1LhiRsGlVGuVgOrkQguJXdeV", customer=self.owner.stripe_customer_id
        )
        c_mock.assert_called_once_with(
            self.owner.stripe_customer_id,
            invoice_settings={"default_payment_method": "pm_1LhiRsGlVGuVgOrkQguJXdeV"},
        )

    @patch("billing.views.StripeWebhookHandler._has_unverified_initial_payment_method")
    @patch("services.billing.stripe.PaymentMethod.attach")
    @patch("services.billing.stripe.Customer.modify")
    def test_customer_subscription_updated_sets_fields_on_success_multiple_owner(
        self,
        c_mock,
        pm_mock,
        has_unverified_initial_payment_method_mock,
    ):
        has_unverified_initial_payment_method_mock.return_value = False
        self.add_second_owner()
        self.owner.plan = "users-free"
        self.owner.plan_user_count = 5
        self.owner.plan_auto_activate = False
        self.other_owner.plan = "users-free"
        self.other_owner.plan_user_count = 5
        self.other_owner.plan_auto_activate = False

        plan_name = "users-pr-inappy"
        quantity = 20

        self._send_event(
            payload={
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id,
                        "plan": {"id": "plan_pro_yearly"},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": quantity,
                        "status": "active",
                        "schedule": None,
                        "default_payment_method": "pm_1LhiRsGlVGuVgOrkQguJXdeV",
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        self.other_owner.refresh_from_db()
        assert self.owner.plan == plan_name
        assert self.owner.plan_user_count == quantity
        assert self.owner.plan_auto_activate == True
        assert self.other_owner.plan == plan_name
        assert self.other_owner.plan_user_count == quantity
        assert self.other_owner.plan_auto_activate == True
        pm_mock.assert_called_once_with(
            "pm_1LhiRsGlVGuVgOrkQguJXdeV", customer=self.owner.stripe_customer_id
        )
        c_mock.assert_called_once_with(
            self.owner.stripe_customer_id,
            invoice_settings={"default_payment_method": "pm_1LhiRsGlVGuVgOrkQguJXdeV"},
        )

    @patch("logging.Logger.error")
    def test_customer_subscription_updated_logs_error_if_no_matching_owners(
        self, log_error_mock
    ):
        self._send_event(
            payload={
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": "sub_notexist",
                        "customer": "cus_notexist",
                        "plan": {"id": "plan_pro_yearly"},
                        "metadata": {"obo_organization": 1},
                        "quantity": 8,
                        "status": "active",
                        "schedule": None,
                        "default_payment_method": "pm_1LhiRsGlVGuVgOrkQguJXdeV",
                    }
                },
            }
        )

        log_error_mock.assert_called_with(
            "Subscription update requested with for plan attached to no owners",
            extra={
                "stripe_subscription_id": "sub_notexist",
                "stripe_customer_id": "cus_notexist",
                "plan_id": "plan_pro_yearly",
            },
        )

    @patch("services.billing.stripe.Subscription.retrieve")
    def test_subscription_schedule_released_updates_owner_with_existing_subscription(
        self, retrieve_subscription_mock
    ):
        self.owner.plan = "users-pr-inappy"
        self.owner.plan_user_count = 10
        self.owner.save()

        self.new_params = {
            "new_plan": "plan_pro_yearly",
            "new_quantity": 7,
            "subscription_id": "sub_123",
        }

        retrieve_subscription_mock.return_value = MockSubscription(
            self.owner, self.new_params
        )

        self._send_event(
            payload={
                "type": "subscription_schedule.released",
                "data": {
                    "object": {
                        "released_subscription": "sub_sched_1K8xfkGlVGuVgOrkxvroyZdH"
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        plan = Plan.objects.get(stripe_id=self.new_params["new_plan"])
        assert self.owner.plan == plan.name
        assert self.owner.plan_user_count == self.new_params["new_quantity"]

    @patch("services.billing.stripe.Subscription.retrieve")
    def test_subscription_schedule_released_updates_multiple_owners_with_existing_subscription(
        self, retrieve_subscription_mock
    ):
        self.add_second_owner()
        self.owner.plan = "users-pr-inappy"
        self.owner.plan_user_count = 10
        self.owner.save()
        self.other_owner.plan = "users-pr-inappy"
        self.other_owner.plan_user_count = 10
        self.other_owner.save()

        self.new_params = {
            "new_plan": "plan_pro_yearly",
            "new_quantity": 7,
            "subscription_id": "sub_123",
        }

        retrieve_subscription_mock.return_value = MockSubscription(
            self.owner, self.new_params
        )

        self._send_event(
            payload={
                "type": "subscription_schedule.released",
                "data": {
                    "object": {
                        "released_subscription": "sub_sched_1K8xfkGlVGuVgOrkxvroyZdH"
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        self.other_owner.refresh_from_db()

        plan = Plan.objects.get(stripe_id=self.new_params["new_plan"])
        assert self.owner.plan == plan.name
        assert self.owner.plan_user_count == self.new_params["new_quantity"]
        assert self.other_owner.plan == plan.name
        assert self.other_owner.plan_user_count == self.new_params["new_quantity"]

    @patch("logging.Logger.error")
    @patch("services.billing.stripe.Subscription.retrieve")
    def test_subscription_schedule_released_logs_error_if_owner_does_not_exist(
        self,
        retrieve_subscription_mock,
        log_error_mock,
    ):
        self.new_params = {
            "new_plan": "plan_pro_yearly",
            "new_quantity": 7,
            "subscription_id": "sub_notexist",
        }

        retrieve_subscription_mock.return_value = MockSubscription(
            self.owner, self.new_params
        )

        self._send_event(
            payload={
                "type": "subscription_schedule.released",
                "data": {
                    "object": {
                        "released_subscription": "sub_sched_1K8xfkGlVGuVgOrkxvroyZdH"
                    }
                },
            }
        )

        log_error_mock.assert_called_with(
            "Subscription schedule released requested with invalid subscription",
            extra={
                "stripe_subscription_id": "sub_notexist",
                "stripe_customer_id": "cus_123",
                "plan_id": "plan_pro_yearly",
            },
        )

    @patch("services.billing.stripe.Subscription.retrieve")
    def test_subscription_schedule_created_logs_a_new_schedule(
        self, retrieve_subscription_mock
    ):
        original_plan = "users-pr-inappy"
        original_quantity = 10
        subscription_id = "sub_1K8xfkGlVGuVgOrkxvroyZdH"
        self.owner.plan = original_plan
        self.owner.plan_user_count = original_quantity
        self.owner.save()

        self.params = {
            "new_plan": "plan_pro_yearly",
            "new_quantity": 7,
            "subscription_id": subscription_id,
        }

        retrieve_subscription_mock.return_value = MockSubscription(
            self.owner, self.params
        )

        self._send_event(
            payload={
                "type": "subscription_schedule.created",
                "data": {"object": {"subscription": subscription_id}},
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.plan == original_plan
        assert self.owner.plan_user_count == original_quantity

    @patch("services.billing.stripe.Subscription.retrieve")
    def test_subscription_schedule_updated_logs_changes_to_schedule(
        self, retrieve_subscription_mock
    ):
        original_plan = "users-pr-inappy"
        original_quantity = 10
        subscription_id = "sub_1K8xfkGlVGuVgOrkxvroyZdH"
        new_plan = "plan_pro_yearly"
        new_quantity = 7
        self.owner.plan = original_plan
        self.owner.plan_user_count = original_quantity
        self.owner.save()

        self.params = {
            "new_plan": new_plan,
            "new_quantity": new_quantity,
            "subscription_id": subscription_id,
        }

        retrieve_subscription_mock.return_value = MockSubscription(
            self.owner, self.params
        )

        self._send_event(
            payload={
                "type": "subscription_schedule.updated",
                "data": {
                    "object": {
                        "subscription": subscription_id,
                        "phases": [
                            {},
                            {"items": [{"plan": new_plan, "quantity": new_quantity}]},
                        ],
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.plan == original_plan
        assert self.owner.plan_user_count == original_quantity

    def test_checkout_session_completed_sets_stripe_ids(self):
        self.owner.stripe_customer_id = None
        self.owner.save()

        expected_customer_id = "cus_1234"
        expected_subscription_id = "sub_7890"

        self._send_event(
            payload={
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "customer": expected_customer_id,
                        "client_reference_id": str(self.owner.ownerid),
                        "subscription": expected_subscription_id,
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.stripe_customer_id == expected_customer_id
        assert self.owner.stripe_subscription_id == expected_subscription_id

    @patch("billing.views.stripe.Subscription.modify")
    def test_customer_update_but_not_payment_method(self, subscription_modify_mock):
        payment_method = "pm_123"
        self._send_event(
            payload={
                "type": "customer.updated",
                "data": {
                    "object": {
                        "invoice_settings": {"default_payment_method": None},
                        "subscriptions": {
                            "data": [{"default_payment_method": payment_method}]
                        },
                    }
                },
            }
        )

        subscription_modify_mock.assert_not_called()

    @patch("billing.views.stripe.Subscription.modify")
    def test_customer_update_but_payment_method_is_same(self, subscription_modify_mock):
        payment_method = "pm_123"
        self._send_event(
            payload={
                "type": "customer.updated",
                "data": {
                    "object": {
                        "invoice_settings": {"default_payment_method": payment_method},
                        "subscriptions": {
                            "data": [{"default_payment_method": payment_method}]
                        },
                    }
                },
            }
        )

        subscription_modify_mock.assert_not_called()

    @patch("billing.views.stripe.Subscription.modify")
    def test_customer_update_payment_method(self, subscription_modify_mock):
        payment_method = "pm_123"
        old_payment_method = "pm_321"
        self._send_event(
            payload={
                "type": "customer.updated",
                "data": {
                    "object": {
                        "id": "cus_123",
                        "invoice_settings": {"default_payment_method": payment_method},
                        "subscriptions": {
                            "data": [
                                {
                                    "id": "sub_123",
                                    "default_payment_method": old_payment_method,
                                }
                            ]
                        },
                    }
                },
            }
        )

        subscription_modify_mock.assert_called_once_with(
            "sub_123", default_payment_method=payment_method
        )

    @patch("services.billing.stripe.PaymentIntent.retrieve")
    @patch("services.billing.stripe.Invoice.retrieve")
    def test_has_unverified_initial_payment_method(
        self, invoice_retrieve_mock, payment_intent_retrieve_mock
    ):
        subscription = Mock()
        subscription.latest_invoice = "inv_123"

        class MockPaymentIntent:
            status = "requires_action"

        invoice_retrieve_mock.return_value = Mock(payment_intent="pi_123")
        payment_intent_retrieve_mock.return_value = stripe.PaymentIntent.construct_from(
            {
                "status": "requires_action",
                "next_action": {"type": "verify_with_microdeposits"},
            },
            "payment_intent_asdf",
        )

        handler = StripeWebhookHandler()
        result = handler._has_unverified_initial_payment_method(subscription)

        assert result is True
        invoice_retrieve_mock.assert_called_once_with("inv_123")
        payment_intent_retrieve_mock.assert_called_once_with("pi_123")

    @patch("services.billing.stripe.PaymentIntent.retrieve")
    @patch("services.billing.stripe.Invoice.retrieve")
    def test_has_unverified_initial_payment_method_no_payment_intent(
        self, invoice_retrieve_mock, payment_intent_retrieve_mock
    ):
        subscription = Mock()
        subscription.latest_invoice = "inv_123"

        invoice_retrieve_mock.return_value = Mock(payment_intent=None)

        handler = StripeWebhookHandler()
        result = handler._has_unverified_initial_payment_method(subscription)

        assert result is False
        invoice_retrieve_mock.assert_called_once_with("inv_123")
        payment_intent_retrieve_mock.assert_not_called()

    @patch("services.billing.stripe.PaymentIntent.retrieve")
    @patch("services.billing.stripe.Invoice.retrieve")
    def test_has_unverified_initial_payment_method_payment_intent_succeeded(
        self, invoice_retrieve_mock, payment_intent_retrieve_mock
    ):
        subscription = stripe.Subscription.construct_from(
            {"latest_invoice": "inv_123"}, "sub_123"
        )

        invoice_retrieve_mock.return_value = stripe.Invoice.construct_from(
            {"payment_intent": "pi_123"}, "inv_123"
        )
        payment_intent_retrieve_mock.return_value = stripe.PaymentIntent.construct_from(
            {"status": "succeeded"}, "payment_intent_asdf"
        )

        handler = StripeWebhookHandler()
        result = handler._has_unverified_initial_payment_method(subscription)

        assert result is False
        invoice_retrieve_mock.assert_called_once_with("inv_123")
        payment_intent_retrieve_mock.assert_called_once_with("pi_123")

    @patch("services.billing.stripe.PaymentMethod.attach")
    @patch("services.billing.stripe.Customer.modify")
    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.PaymentMethod.retrieve")
    def test_check_and_handle_delayed_notification_payment_methods(
        self,
        payment_method_retrieve_mock,
        subscription_modify_mock,
        customer_modify_mock,
        payment_method_attach_mock,
    ):
        class MockPaymentMethod:
            type = "us_bank_account"
            us_bank_account = {}
            id = "pm_123"

        payment_method_retrieve_mock.return_value = MockPaymentMethod()

        self.owner.stripe_subscription_id = "sub_123"
        self.owner.stripe_customer_id = "cus_123"
        self.owner.save()

        handler = StripeWebhookHandler()
        handler._check_and_handle_delayed_notification_payment_methods(
            "cus_123", "pm_123"
        )

        payment_method_retrieve_mock.assert_called_once_with("pm_123")
        payment_method_attach_mock.assert_called_once_with(
            payment_method_retrieve_mock.return_value, customer="cus_123"
        )
        customer_modify_mock.assert_called_once_with(
            "cus_123",
            invoice_settings={
                "default_payment_method": payment_method_retrieve_mock.return_value
            },
        )
        subscription_modify_mock.assert_called_once_with(
            "sub_123", default_payment_method=payment_method_retrieve_mock.return_value
        )

    @patch("logging.Logger.error")
    @patch("services.billing.stripe.PaymentMethod.attach")
    @patch("services.billing.stripe.Customer.modify")
    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.PaymentMethod.retrieve")
    def test_check_and_handle_delayed_notification_payment_methods_no_subscription(
        self,
        payment_method_retrieve_mock,
        subscription_modify_mock,
        customer_modify_mock,
        payment_method_attach_mock,
        log_error_mock,
    ):
        class MockPaymentMethod:
            type = "us_bank_account"
            us_bank_account = {}
            id = "pm_123"

        payment_method_retrieve_mock.return_value = MockPaymentMethod()

        self.owner.stripe_subscription_id = None
        self.owner.stripe_customer_id = "cus_123"
        self.owner.save()

        handler = StripeWebhookHandler()
        handler._check_and_handle_delayed_notification_payment_methods(
            "cus_123", "pm_123"
        )

        payment_method_retrieve_mock.assert_called_once_with("pm_123")
        payment_method_attach_mock.assert_not_called()
        customer_modify_mock.assert_not_called()
        subscription_modify_mock.assert_not_called()

        log_error_mock.assert_called_once_with(
            "No owners found with that customer_id, something went wrong",
            extra=dict(customer_id="cus_123"),
        )

    @patch("logging.Logger.error")
    @patch("services.billing.stripe.PaymentMethod.attach")
    @patch("services.billing.stripe.Customer.modify")
    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.PaymentMethod.retrieve")
    def test_check_and_handle_delayed_notification_payment_methods_no_customer(
        self,
        payment_method_retrieve_mock,
        subscription_modify_mock,
        customer_modify_mock,
        payment_method_attach_mock,
        log_error_mock,
    ):
        class MockPaymentMethod:
            type = "us_bank_account"
            us_bank_account = {}
            id = "pm_123"

        payment_method_retrieve_mock.return_value = MockPaymentMethod()

        handler = StripeWebhookHandler()
        handler._check_and_handle_delayed_notification_payment_methods(
            "cus_1", "pm_123"
        )

        payment_method_retrieve_mock.assert_called_once_with("pm_123")
        payment_method_attach_mock.assert_not_called()
        customer_modify_mock.assert_not_called()
        subscription_modify_mock.assert_not_called()

        log_error_mock.assert_called_once_with(
            "No owners found with that customer_id, something went wrong",
            extra=dict(customer_id="cus_1"),
        )

    @patch("services.billing.stripe.PaymentMethod.attach")
    @patch("services.billing.stripe.Customer.modify")
    @patch("services.billing.stripe.Subscription.modify")
    @patch("services.billing.stripe.PaymentMethod.retrieve")
    def test_check_and_handle_delayed_notification_payment_methods_multiple_subscriptions(
        self,
        payment_method_retrieve_mock,
        subscription_modify_mock,
        customer_modify_mock,
        payment_method_attach_mock,
    ):
        class MockPaymentMethod:
            type = "us_bank_account"
            us_bank_account = {}
            id = "pm_123"

        payment_method_retrieve_mock.return_value = MockPaymentMethod()

        self.owner.stripe_subscription_id = "sub_123"
        self.owner.stripe_customer_id = "cus_123"
        self.owner.save()

        OwnerFactory(stripe_subscription_id="sub_124", stripe_customer_id="cus_123")

        handler = StripeWebhookHandler()
        handler._check_and_handle_delayed_notification_payment_methods(
            "cus_123", "pm_123"
        )

        payment_method_retrieve_mock.assert_called_once_with("pm_123")
        payment_method_attach_mock.assert_called_once_with(
            payment_method_retrieve_mock.return_value, customer="cus_123"
        )
        customer_modify_mock.assert_called_once_with(
            "cus_123",
            invoice_settings={
                "default_payment_method": payment_method_retrieve_mock.return_value
            },
        )
        subscription_modify_mock.assert_has_calls(
            [
                call(
                    "sub_123",
                    default_payment_method=payment_method_retrieve_mock.return_value,
                ),
                call(
                    "sub_124",
                    default_payment_method=payment_method_retrieve_mock.return_value,
                ),
            ]
        )

    @patch(
        "billing.views.StripeWebhookHandler._check_and_handle_delayed_notification_payment_methods"
    )
    @patch("logging.Logger.info")
    def test_payment_intent_succeeded(
        self, log_info_mock, check_and_handle_delayed_notification_mock
    ):
        class MockPaymentIntent:
            id = "pi_123"
            customer = "cus_123"
            payment_method = "pm_123"

        handler = StripeWebhookHandler()
        handler.payment_intent_succeeded(MockPaymentIntent())

        check_and_handle_delayed_notification_mock.assert_called_once_with(
            "cus_123", "pm_123"
        )
        log_info_mock.assert_called_once_with(
            "Payment intent succeeded",
            extra=dict(
                stripe_customer_id="cus_123",
                payment_intent_id="pi_123",
                payment_method_type="pm_123",
            ),
        )

    @patch(
        "billing.views.StripeWebhookHandler._check_and_handle_delayed_notification_payment_methods"
    )
    @patch("logging.Logger.info")
    def test_setup_intent_succeeded(
        self, log_info_mock, check_and_handle_delayed_notification_mock
    ):
        class MockSetupIntent:
            id = "seti_123"
            customer = "cus_123"
            payment_method = "pm_123"

        handler = StripeWebhookHandler()
        handler.setup_intent_succeeded(MockSetupIntent())

        check_and_handle_delayed_notification_mock.assert_called_once_with(
            "cus_123", "pm_123"
        )
        log_info_mock.assert_called_once_with(
            "Setup intent succeeded",
            extra=dict(
                stripe_customer_id="cus_123",
                setup_intent_id="seti_123",
                payment_method_type="pm_123",
            ),
        )
