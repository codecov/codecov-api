import unittest
from unittest.mock import Mock, patch

from django.test import TestCase

from billing.views import StripeWebhookHandler
from codecov_auth.tests.factories import OwnerFactory


class TestInvoicePaymentSucceeded(TestCase):
    def setUp(self):
        self.handler = StripeWebhookHandler()
        self.owner = OwnerFactory(
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
        )

    @patch("billing.views.Owner.objects.filter")
    def test_invoice_payment_succeeded_updates_delinquent_status(self, mock_filter):
        mock_owners = Mock()
        mock_filter.return_value = mock_owners

        # Create a mock invoice object
        mock_invoice = Mock()
        mock_invoice.customer = self.owner.stripe_customer_id
        mock_invoice.subscription = self.owner.stripe_subscription_id
        mock_invoice.total = 24000
        mock_invoice.hosted_invoice_url = "https://stripe.com"

        # Call the handler method
        self.handler.invoice_payment_succeeded(mock_invoice)

        # Verify the owners were filtered and updated correctly
        mock_filter.assert_called_once_with(
            stripe_customer_id=self.owner.stripe_customer_id,
        )
        mock_owners.update.assert_called_once_with(delinquent=False)

    @patch("billing.views.Owner.objects.filter")
    @patch("billing.views.TaskService")
    def test_invoice_payment_succeeded_sends_email_to_delinquent_owners(
        self, mock_task_service, mock_filter
    ):
        # Setup mock owners with delinquent status
        mock_owners = Mock()
        mock_owners_list = [self.owner]
        mock_filter.return_value = mock_owners
        mock_owners.filter.return_value = mock_owners
        mock_owners.__iter__.return_value = mock_owners_list
        
        # Setup delinquent status
        self.owner.delinquent = True
        self.owner.email = "test@example.com"
        
        # Setup task service mock
        mock_task_service_instance = Mock()
        mock_task_service.return_value = mock_task_service_instance

        # Create a mock invoice object
        mock_invoice = Mock()
        mock_invoice.customer = self.owner.stripe_customer_id
        mock_invoice.subscription = self.owner.stripe_subscription_id
        mock_invoice.total = 24000
        mock_invoice.hosted_invoice_url = "https://stripe.com"

        # Call the handler method
        self.handler.invoice_payment_succeeded(mock_invoice)

        # Verify email was sent to delinquent owner
        mock_task_service_instance.send_email.assert_called_with(
            to_addr=self.owner.email,
            subject="You're all set",
            template_name="success-after-failed-payment",
            amount=240,
            cta_link="https://stripe.com",
            date=unittest.mock.ANY,
        )


class TestInvoicePaymentFailed(TestCase):
    def setUp(self):
        self.handler = StripeWebhookHandler()
        self.owner = OwnerFactory(
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
            delinquent=False
        )

    @patch("billing.views.stripe.PaymentIntent.retrieve")
    @patch("billing.views.Owner.objects.filter")
    def test_invoice_payment_failed_with_payment_method_sets_delinquent(
        self, mock_filter, mock_retrieve_payment_intent
    ):
        # Setup mock owners
        mock_owners = Mock()
        mock_filter.return_value = mock_owners

        # Create a mock invoice object with payment method
        mock_invoice = Mock()
        mock_invoice.customer = self.owner.stripe_customer_id
        mock_invoice.subscription = self.owner.stripe_subscription_id
        mock_invoice.total = 24000
        mock_invoice.hosted_invoice_url = "https://stripe.com"
        mock_invoice.payment_intent = "pi_123"
        mock_invoice.default_payment_method = {}  # Not None

        # Call the handler method
        self.handler.invoice_payment_failed(mock_invoice)

        # Verify owners were set to delinquent
        mock_owners.update.assert_called_once_with(delinquent=True)

    @patch("billing.views.stripe.PaymentIntent.retrieve")
    @patch("billing.views.Owner.objects.filter")
    def test_invoice_payment_failed_skips_delinquency_for_requires_action(
        self, mock_filter, mock_retrieve_payment_intent
    ):
        # Setup payment intent that requires action
        mock_payment_intent = Mock()
        mock_payment_intent.status = "requires_action"
        mock_payment_intent.next_action = {"type": "verify_with_microdeposits"}
        mock_retrieve_payment_intent.return_value = mock_payment_intent

        # Create a mock invoice object with no payment method
        mock_invoice = Mock()
        mock_invoice.payment_intent = "pi_123"
        mock_invoice.default_payment_method = None

        # No delinquent status should be set for this case
        self.handler.invoice_payment_failed(mock_invoice)
        mock_filter.assert_not_called()