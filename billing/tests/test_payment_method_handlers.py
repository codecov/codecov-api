from unittest.mock import Mock, patch

from django.test import TestCase

from billing.views import StripeWebhookHandler
from codecov_auth.tests.factories import OwnerFactory


class TestPaymentMethodHandlers(TestCase):
    def setUp(self):
        self.handler = StripeWebhookHandler()
        self.owner = OwnerFactory(
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
        )

    @patch("billing.views.stripe.PaymentMethod.attach")
    @patch("billing.views.stripe.Customer.modify")
    @patch("billing.views.stripe.Subscription.modify")
    @patch("billing.views.stripe.PaymentMethod.retrieve")
    @patch("billing.views.Owner.objects.filter")
    def test_check_and_handle_delayed_notification_payment_methods(
        self,
        mock_filter,
        mock_retrieve,
        mock_sub_modify,
        mock_customer_modify,
        mock_attach,
    ):
        # Setup mock owners
        mock_owners = Mock()
        mock_filter.return_value = mock_owners
        mock_owners.values_list.return_value = [["sub_123"]]

        # Setup mock payment method
        mock_payment_method = Mock()
        mock_payment_method.type = "us_bank_account"
        mock_payment_method.us_bank_account = {}
        mock_payment_method.id = "pm_123"
        mock_retrieve.return_value = mock_payment_method

        # Call the handler method
        self.handler._check_and_handle_delayed_notification_payment_methods(
            "cus_123", "pm_123"
        )

        # Verify payment method was attached to customer
        mock_attach.assert_called_once_with(mock_payment_method, customer="cus_123")
        
        # Verify customer was updated with default payment method
        mock_customer_modify.assert_called_once_with(
            "cus_123",
            invoice_settings={"default_payment_method": mock_payment_method},
        )
        
        # Verify subscription was updated with default payment method
        mock_sub_modify.assert_called_once_with(
            "sub_123", 
            default_payment_method=mock_payment_method
        )

    @patch("billing.views.logging.Logger.info")
    @patch("billing.views.StripeWebhookHandler._check_and_handle_delayed_notification_payment_methods")
    def test_payment_intent_succeeded(self, mock_check, mock_log_info):
        # Create mock payment intent
        mock_payment_intent = Mock()
        mock_payment_intent.id = "pi_123"
        mock_payment_intent.customer = "cus_123"
        mock_payment_intent.payment_method = "pm_123"

        # Call the handler method
        self.handler.payment_intent_succeeded(mock_payment_intent)

        # Verify delayed notification method was called
        mock_check.assert_called_once_with("cus_123", "pm_123")
