import stripe
import json
import time

from unittest.mock import patch

from django.conf import settings

from rest_framework.test import APITestCase
from rest_framework.reverse import reverse
from rest_framework import status

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory

from ..constants import StripeHTTPHeaders


class StripeWebhookHandlerTests(APITestCase):
    def setUp(self):
        self.owner = OwnerFactory(stripe_customer_id="20f0", stripe_subscription_id="3p00")

    def _send_event(self, payload):
        timestamp = time.time_ns()

        return self.client.post(
            reverse("stripe-webhook"),
            **{
                StripeHTTPHeaders.SIGNATURE: "t={},v1={}".format(
                    timestamp,
                    stripe.WebhookSignature._compute_signature(
                        "{}.{}".format(timestamp, json.dumps(payload)),
                        settings.STRIPE_ENDPOINT_SECRET
                    )
                )
            },
            data=payload,
            format="json"
        )

    def test_invoice_payment_succeeded_sets_owner_delinquent_false(self):
        self.owner.deliquent = True
        self.owner.save()

        response = self._send_event(
            payload={
                "type": "invoice.payment_succeeded",
                "data": {
                    "object": {
                        "customer": self.owner.stripe_customer_id,
                        "subscription": {
                            "id": self.owner.stripe_subscription_id
                        }
                    }
                }
            }
        )

        self.owner.refresh_from_db()
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert self.owner.delinquent is False

    def test_invoice_payment_failed_sets_owner_delinquent_true(self):
        self.owner.delinquent = False
        self.owner.save()

        response = self._send_event(
            payload={
                "type": "invoice.payment_failed",
                "data": {
                    "object": {
                        "customer": self.owner.stripe_customer_id,
                        "subscription": {
                            "id": self.owner.stripe_subscription_id
                        }
                    }
                }
            }
        )

        self.owner.refresh_from_db()
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert self.owner.delinquent is True

    @patch('codecov_auth.models.Owner.set_free_plan')
    def test_customer_subscription_deleted_sets_plan_to_free(self, set_free_plan_mock):
        self.owner.plan = "users-inappy"
        self.owner.plan_user_count = 20
        self.owner.save()

        response = self._send_event(
            payload={
                "type": "customer.subscription.deleted",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id
                    }
                }
            }
        )

        set_free_plan_mock.assert_called_once()

    def test_customer_subscription_deleted_deactivates_all_repos(self):
        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.owner, activated=True, active=True)

        assert self.owner.repository_set.filter(activated=True, active=True).count() == 3

        response = self._send_event(
            payload={
                "type": "customer.subscription.deleted",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id
                    }
                }
            }
        )

        assert self.owner.repository_set.filter(activated=True, active=True).count() == 0

    def test_customer_created_logs_and_doesnt_crash(self):
        response = self._send_event(
            payload={
                "type": "customer.created",
                "data": {
                    "object": {
                        "id": "FOEKDCDEQ",
                        "email": "test@email.com"
                    }
                }
            }
        )

    def test_customer_subscription_created_does_nothing_if_no_plan_id(self):
        self.owner.stripe_subscription_id = None
        self.owner.stripe_customer_id = None
        self.owner.save()

        response = self._send_event(
            payload={
                "type": "customer.subscription.created",
                "data": {
                    "object": {
                        "id": "FOEKDCDEQ",
                        "customer": "sdo050493",
                        "plan": {
                            "id": None,
                            "name": "users-inappy"
                        },
                        "metadata": {
                            "obo_organization": self.owner.ownerid
                        },
                        "quantity": 20
                    }
                }
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.stripe_subscription_id == None
        assert self.owner.stripe_customer_id == None

    def test_customer_subscription_created_does_nothing_if_plan_not_paid_user_plan(self):
        self.owner.stripe_subscription_id = None
        self.owner.stripe_customer_id = None
        self.owner.save()

        response = self._send_event(
            payload={
                "type": "customer.subscription.created",
                "data": {
                    "object": {
                        "id": "FOEKDCDEQ",
                        "customer": "sdo050493",
                        "plan": {
                            "id": "fieown4",
                            "name": "users-free"
                        },
                        "metadata": {
                            "obo_organization": self.owner.ownerid
                        },
                        "quantity": 20
                    }
                }
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.stripe_subscription_id == None
        assert self.owner.stripe_customer_id == None

    def test_customer_subscription_created_sets_plan_info(self):
        self.owner.stripe_subscription_id = None
        self.owner.stripe_customer_id = None
        self.owner.save()

        stripe_subscription_id = "FOEKDCDEQ"
        stripe_customer_id = "sdo050493"
        plan_name = "users-inappy"
        quantity = 20

        response = self._send_event(
            payload={
                "type": "customer.subscription.created",
                "data": {
                    "object": {
                        "id": stripe_subscription_id,
                        "customer": stripe_customer_id,
                        "plan": {
                            "id": "fieown4",
                            "name": plan_name
                        },
                        "metadata": {
                            "obo_organization": self.owner.ownerid
                        },
                        "quantity": quantity
                    }
                }
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.stripe_subscription_id == stripe_subscription_id
        assert self.owner.stripe_customer_id == stripe_customer_id
        assert self.owner.plan_user_count == quantity
        assert self.owner.plan_auto_activate is True
        assert self.owner.plan == plan_name
