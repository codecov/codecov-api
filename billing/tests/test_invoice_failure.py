import unittest
from datetime import datetime
from unittest.mock import Mock, call, patch

import stripe
from django.test import TestCase
from rest_framework.test import APITestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from billing.views import StripeWebhookHandler


class MockCard(object):
    def __init__(self):
        self.brand = "visa"
        self.last4 = "1234"

    def __getitem__(self, key):
        return getattr(self, key)


class MockPaymentMethod(object):
    def __init__(self, noCard=False):
        if noCard:
            self.card = None
            return

        self.card = MockCard()

    def __getitem__(self, key):
        return getattr(self, key)


class MockPaymentIntent(object):
    def __init__(self, noCard=False, status="succeeded", next_action=None):
        self.payment_method = MockPaymentMethod(noCard)
        self.status = status
        self.next_action = next_action or {}

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


class InvoiceFailureTests(TestCase):
    def setUp(self):
        self.owner = OwnerFactory(
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
            delinquent=False,
        )
        self.handler = StripeWebhookHandler()

    @patch("stripe.PaymentIntent.retrieve")
    def test_invoice_payment_failed_skips_delinquency_for_microdeposit_verification(self, mock_retrieve):
        """Test that delinquency is skipped when waiting for microdeposit verification"""
        # Set up the payment intent to indicate microdeposit verification
        mock_retrieve.return_value = MockPaymentIntent(
            status="requires_action", 
            next_action={"type": "verify_with_microdeposits"}
        )
        
        # Create a mock invoice
        mock_invoice = Mock()
        mock_invoice.customer = self.owner.stripe_customer_id
        mock_invoice.subscription = self.owner.stripe_subscription_id
        mock_invoice.default_payment_method = None
        mock_invoice.payment_intent = "pi_123"
        
        # Call the method being tested
        self.handler.invoice_payment_failed(mock_invoice)
        
        # Verify owner delinquent status was not changed
        self.owner.refresh_from_db()
        self.assertFalse(self.owner.delinquent)
        
        # Verify payment intent was retrieved
        mock_retrieve.assert_called_once_with("pi_123")

    @patch("stripe.PaymentIntent.retrieve")
    @patch("services.task.TaskService.send_email")
    def test_invoice_payment_failed_sets_delinquent_true(self, mock_send_email, mock_retrieve):
        """Test that invoice_payment_failed sets delinquent status to True"""
        # Setup payment intent with a normal failure (not microdeposits)
        mock_retrieve.return_value = MockPaymentIntent()
        
        # Create a mock invoice
        mock_invoice = Mock()
        mock_invoice.customer = self.owner.stripe_customer_id
        mock_invoice.subscription = self.owner.stripe_subscription_id
        mock_invoice.total = 24000
        mock_invoice.hosted_invoice_url = "https://stripe.com/invoice"
        mock_invoice.default_payment_method = {}
        mock_invoice.payment_intent = "pi_123"
        mock_invoice.__getitem__ = lambda self, key: getattr(self, key)
        
        # Call the method being tested
        self.handler.invoice_payment_failed(mock_invoice)
        
        # Verify owner delinquent status was changed
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.delinquent)
        
        # Verify email was sent to owner
        mock_send_email.assert_called_with(
            to_addr=self.owner.email,
            subject="Your Codecov payment failed",
            template_name="failed-payment",
            name=self.owner.username,
            amount=240,
            card_type="visa",
            last_four="1234",
            cta_link="https://stripe.com/invoice",
            date=datetime.now().strftime("%B %-d, %Y"),
        )

    @patch("stripe.PaymentIntent.retrieve")
    @patch("services.task.TaskService.send_email")
    def test_invoice_payment_failed_with_multiple_admins(self, mock_send_email, mock_retrieve):
        """Test that invoice_payment_failed sends emails to all admins"""
        # Create admin owners
        admin_1 = OwnerFactory(email="admin1@example.com", username="admin1")
        admin_2 = OwnerFactory(email="admin2@example.com", username="admin2")
        
        # Set admins for the owner
        self.owner.admins = [admin_1.ownerid, admin_2.ownerid]
        self.owner.save()
        
        # Setup payment intent with normal failure
        mock_retrieve.return_value = MockPaymentIntent()
        
        # Create a mock invoice
        mock_invoice = Mock()
        mock_invoice.customer = self.owner.stripe_customer_id
        mock_invoice.subscription = self.owner.stripe_subscription_id
        mock_invoice.total = 24000
        mock_invoice.hosted_invoice_url = "https://stripe.com/invoice"
        mock_invoice.default_payment_method = {}
        mock_invoice.payment_intent = "pi_123"
        mock_invoice.__getitem__ = lambda self, key: getattr(self, key)
        
        # Call the method being tested
        self.handler.invoice_payment_failed(mock_invoice)
        
        # Verify owner delinquent status was changed
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.delinquent)
        
        # Verify emails were sent to owner and all admins
        self.assertEqual(mock_send_email.call_count, 3)
        mock_send_email.assert_any_call(
            to_addr=admin_1.email,
            subject="Your Codecov payment failed",
            template_name="failed-payment",
            name=admin_1.username,
            amount=240,
            card_type="visa",
            last_four="1234",
            cta_link="https://stripe.com/invoice",
            date=datetime.now().strftime("%B %-d, %Y"),
        )