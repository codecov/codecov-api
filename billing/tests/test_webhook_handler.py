import unittest
from unittest.mock import patch, MagicMock

import stripe
from django.test import TestCase

from billing.views import StripeWebhookHandler


class TestStripeWebhookHandler(TestCase):
    def setUp(self):
        self.handler = StripeWebhookHandler()

    @patch("billing.views.stripe.Subscription.modify")
    @patch("billing.views.stripe.Customer.modify")
    @patch("billing.views.stripe.PaymentMethod.attach")
    def test_customer_subscription_updated_without_payment_failure_detection(
        self, mock_attach, mock_customer_modify, mock_subscription_modify
    ):
        # Create a mock subscription with a default_payment_method
        mock_subscription = MagicMock()
        mock_subscription.id = "sub_123"
        mock_subscription.customer = "cus_456"
        mock_subscription.default_payment_method = "pm_789"
        # Include pending_update which previously would have triggered delinquent status
        mock_subscription.pending_update = {
            "expires_at": 1571194285,
            "subscription_items": [{"id": "si_123", "price": "price_456"}],
        }
        mock_subscription.status = "active"

        # Create a mock owner in the handler's scope
        self.handler.owners = MagicMock()
        
        # Call the method
        self.handler.customer_subscription_updated(mock_subscription)
        
        # Verify that the delinquent status was not set, by checking the owners update wasn't called with delinquent=True
        self.handler.owners.update.assert_not_called()