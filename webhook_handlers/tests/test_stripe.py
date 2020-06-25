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
