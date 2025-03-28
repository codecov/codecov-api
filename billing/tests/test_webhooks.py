import json
from unittest.mock import Mock, patch

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from billing.constants import StripeHTTPHeaders, StripeWebhookEvents
from billing.views import StripeWebhookHandler


class WebhookHandlerTests(APITestCase):
    def setUp(self):
        self.handler = StripeWebhookHandler()
        self.owner = OwnerFactory(
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
        )

    @patch("billing.views.stripe.Webhook.construct_event")
    def test_post_invalid_signature(self, mock_construct_event):
        """Test handling of invalid signature in webhook request"""
        # Set up the mock to raise an exception for invalid signature
        mock_construct_event.side_effect = stripe.error.SignatureVerificationError(
            "Invalid signature", "sig_header"
        )
        
        # Make a POST request to the webhook endpoint
        response = self.client.post(
            reverse("stripe-webhook"),
            data=json.dumps({"type": "test.event"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="invalid_signature"
        )
        
        # Verify response status and message
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data, "Invalid signature")

    @patch("billing.views.stripe.Webhook.construct_event")
    def test_post_unsupported_event_type(self, mock_construct_event):
        """Test handling of unsupported event types"""
        # Create a mock event with an unsupported type
        mock_event = Mock()
        mock_event.type = "unsupported.event"
        mock_construct_event.return_value = mock_event
        
        # Make a POST request to the webhook endpoint
        response = self.client.post(
            reverse("stripe-webhook"),
            data=json.dumps({"type": "unsupported.event"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_signature"
        )
        
        # Verify response status and message
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.data, "Unsupported event type")

    @patch("billing.views.stripe.Webhook.construct_event")
    @patch("billing.views.StripeWebhookHandler.invoice_payment_succeeded")
    def test_post_supported_event_type(self, mock_handler_method, mock_construct_event):
        """Test handling of supported event types"""
        # Create a mock event with a supported type
        mock_event = Mock()
        mock_event.type = "invoice.payment_succeeded"
        mock_event.data = Mock()
        mock_event.data.object = "invoice_object"
        mock_construct_event.return_value = mock_event
        
        # Make a POST request to the webhook endpoint
        response = self.client.post(
            reverse("stripe-webhook"),
            data=json.dumps({"type": "invoice.payment_succeeded"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="valid_signature"
        )
        
        # Verify response status and that the handler method was called
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        mock_handler_method.assert_called_once_with("invoice_object")

    @patch("billing.views.settings")
    @patch("billing.views.logging.critical")
    def test_post_missing_endpoint_secret(self, mock_log_critical, mock_settings):
        """Test logging when endpoint secret is missing"""
        # Set up settings to have no endpoint secret
        mock_settings.STRIPE_ENDPOINT_SECRET = None
        
        # Make a POST request to the webhook endpoint
        response = self.client.post(
            reverse("stripe-webhook"),
            data=json.dumps({"type": "test.event"}),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="any_signature"
        )
        
        # Verify that a critical log was made
        mock_log_critical.assert_called_once_with(
            "Stripe endpoint secret improperly configured -- webhooks will not be processed."
        )