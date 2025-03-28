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
    def __init__(self, noCard=False):
        self.payment_method = MockPaymentMethod(noCard)
        self.status = "succeeded"

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


class InvoiceTests(TestCase):
    def setUp(self):
        self.owner = OwnerFactory(
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
            delinquent=True,
        )
        self.handler = StripeWebhookHandler()

    @patch("services.task.TaskService.send_email")
    def test_invoice_payment_succeeded_sets_delinquent_false(self, mocked_send_email):
        """Test that invoice_payment_succeeded correctly updates delinquent status"""
        # Create a mock invoice object
        mock_invoice = Mock()
        mock_invoice.customer = self.owner.stripe_customer_id
        mock_invoice.subscription = self.owner.stripe_subscription_id
        mock_invoice.total = 24000  # $240.00
        mock_invoice.hosted_invoice_url = "https://stripe.com/invoice"

        # Call the method being tested
        self.handler.invoice_payment_succeeded(mock_invoice)

        # Verify owner was updated
        self.owner.refresh_from_db()
        self.assertFalse(self.owner.delinquent)

        # Verify email was sent to owner
        mocked_send_email.assert_called_once_with(
            to_addr=self.owner.email,
            subject="You're all set",
            template_name="success-after-failed-payment",
            amount=240,
            cta_link="https://stripe.com/invoice",
            date=datetime.now().strftime("%B %-d, %Y"),
        )

    @patch("services.task.TaskService.send_email")
    def test_invoice_payment_succeeded_with_multiple_admins(self, mocked_send_email):
        """Test invoice_payment_succeeded sends emails to all admins"""
        # Create admin owners
        admin_1 = OwnerFactory(email="admin1@example.com")
        admin_2 = OwnerFactory(email="admin2@example.com")
        
        # Set admins for the owner
        self.owner.admins = [admin_1.ownerid, admin_2.ownerid]
        self.owner.save()

        # Create a mock invoice object
        mock_invoice = Mock()
        mock_invoice.customer = self.owner.stripe_customer_id
        mock_invoice.subscription = self.owner.stripe_subscription_id
        mock_invoice.total = 24000  # $240.00
        mock_invoice.hosted_invoice_url = "https://stripe.com/invoice"

        # Call the method being tested
        self.handler.invoice_payment_succeeded(mock_invoice)

        # Verify owner was updated
        self.owner.refresh_from_db()
        self.assertFalse(self.owner.delinquent)

        # Verify emails were sent to owner and admins
        expected_calls = [
            call(
                to_addr=self.owner.email,
                subject="You're all set",
                template_name="success-after-failed-payment",
                amount=240,
                cta_link="https://stripe.com/invoice",
                date=datetime.now().strftime("%B %-d, %Y"),
            ),
            call(
                to_addr=admin_1.email,
                subject="You're all set",
                template_name="success-after-failed-payment",
                amount=240,
                cta_link="https://stripe.com/invoice",
                date=datetime.now().strftime("%B %-d, %Y"),
            ),
            call(
                to_addr=admin_2.email,
                subject="You're all set",
                template_name="success-after-failed-payment",
                amount=240,
                cta_link="https://stripe.com/invoice",
                date=datetime.now().strftime("%B %-d, %Y"),
            ),
        ]
        mocked_send_email.assert_has_calls(expected_calls, any_order=True)

    def test_invoice_payment_succeeded_no_matching_owners(self):
        """Test handling when no matching owners are found"""
        # Create a mock invoice with non-matching customer/subscription
        mock_invoice = Mock()
        mock_invoice.customer = "cus_nonexistent"
        mock_invoice.subscription = "sub_nonexistent"
        
        # This should run without error, just return without action
        self.handler.invoice_payment_succeeded(mock_invoice)
        
        # Verify owner was not updated
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.delinquent)

    def test_invoice_payment_succeeded_multiple_owners(self):
        """Test handling when multiple owners match the customer/subscription"""
        # Create another owner with the same customer/subscription
        other_owner = OwnerFactory(
            stripe_customer_id=self.owner.stripe_customer_id,
            stripe_subscription_id=self.owner.stripe_subscription_id,
            delinquent=True,
        )
        
        # Create a mock invoice object
        mock_invoice = Mock()
        mock_invoice.customer = self.owner.stripe_customer_id
        mock_invoice.subscription = self.owner.stripe_subscription_id
        mock_invoice.total = 24000
        mock_invoice.hosted_invoice_url = "https://stripe.com/invoice"
        
        # Call the method being tested
        self.handler.invoice_payment_succeeded(mock_invoice)
        
        # Verify both owners were updated
        self.owner.refresh_from_db()
        other_owner.refresh_from_db()
        self.assertFalse(self.owner.delinquent)
        self.assertFalse(other_owner.delinquent)