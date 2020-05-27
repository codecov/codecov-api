from django.test import TestCase

from unittest.mock import patch
from stripe.error import StripeError

from services.billing import BillingService, StripeService, BillingException
from codecov_auth.tests.factories import OwnerFactory


class StripeServiceTests(TestCase):
    def setUp(self):
        self.stripe = StripeService()

    @patch('stripe.Invoice.list')
    def test_list_invoices_calls_stripe_invoice_list_with_customer_stripe_id(self, invoice_list_mock):
        owner = OwnerFactory(stripe_customer_id=-1)
        self.stripe.list_invoices(owner)
        invoice_list_mock.assert_called_once_with(customer=owner.stripe_customer_id, limit=10)

    @patch('stripe.Invoice.list')
    def test_list_invoices_raises_billing_exception_if_stripe_exception(self, invoice_list_mock):
        owner = OwnerFactory(stripe_customer_id=100)
        err_code, err_msg = 404, "Not Found"
        invoice_list_mock.side_effect = StripeError(message=err_msg, http_status=err_code)

        with self.assertRaises(BillingException) as e:
            self.stripe.list_invoices(owner)
            assert e.http_status == err_code
            assert e.message == err_msg

    @patch('stripe.Invoice.list')
    def test_list_invoices_returns_emptylist_if_stripe_customer_id_is_None(self, invoice_list_mock):
        owner = OwnerFactory()
        invoices = self.stripe.list_invoices(owner)

        invoice_list_mock.assert_not_called()
        assert invoices == []


class MockPaymentService:
    def list_invoices(self, owner, limit=10):
        return f"{owner.ownerid} {limit}"


class BillingServiceTests(TestCase):
    def setUp(self):
        self.mock_payment_service = MockPaymentService()
        self.billing_service = BillingService(payment_service=self.mock_payment_service)

    def test_default_payment_service_is_stripe(self):
        assert isinstance(BillingService().payment_service, StripeService)

    def test_list_invoices_calls_payment_service_list_invoices_with_limit(self):
        owner = OwnerFactory()
        assert self.billing_service.list_invoices(owner) == self.mock_payment_service.list_invoices(owner)
