import unittest
from datetime import datetime
from unittest.mock import Mock, patch

import stripe
from django.test import TestCase

from billing.views import StripeWebhookHandler
from shared.django_apps.core.tests.factories import OwnerFactory


class TestStripeWebhookHandlerExtensions(TestCase):
    def setUp(self):
        self.owner = OwnerFactory(
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
        )
        self.handler = StripeWebhookHandler()
        
    @patch("logging.Logger.error")
    def test_payment_intent_payment_failed(self, log_error_mock):
        payment_intent = Mock()
        payment_intent.customer = self.owner.stripe_customer_id
        payment_intent.id = "pi_123"
        
        self.handler.payment_intent_payment_failed(payment_intent)
        
        # Verify owner marked as delinquent
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.delinquent)
        
        # Verify error was logged
        log_error_mock.assert_called_once()
    
    @patch("services.task.TaskService.send_email")
    def test_payment_intent_payment_failed_sends_emails(self, mock_send_email):
        # Create admin users
        admin1 = OwnerFactory(email="admin1@example.com")
        admin2 = OwnerFactory(email="admin2@example.com")
        self.owner.admins = [admin1.ownerid, admin2.ownerid]
        self.owner.email = "owner@example.com"
        self.owner.save()
        
        payment_intent = Mock()
        payment_intent.customer = self.owner.stripe_customer_id
        payment_intent.id = "pi_123"
        payment_intent.amount_received = 24000
        
        self.handler.payment_intent_payment_failed(payment_intent)
        
        # Verify emails were sent to owner and admins
        self.assertEqual(mock_send_email.call_count, 3)
    
    @patch("logging.Logger.info")
    def test_charge_refunded(self, log_info_mock):
        charge = Mock()
        charge.id = "ch_123"
        charge.customer = self.owner.stripe_customer_id
        charge.amount_refunded = 5000
        
        self.handler.charge_refunded(charge)
        
        # Verify info was logged
        log_info_mock.assert_called_once()
    
    @patch("services.task.TaskService.send_email")
    def test_charge_refunded_sends_emails(self, mock_send_email):
        # Create admin users
        admin1 = OwnerFactory(email="admin1@example.com")
        admin2 = OwnerFactory(email="admin2@example.com")
        self.owner.admins = [admin1.ownerid, admin2.ownerid]
        self.owner.email = "owner@example.com"
        self.owner.save()
        
        charge = Mock()
        charge.id = "ch_123"
        charge.customer = self.owner.stripe_customer_id
        charge.amount_refunded = 5000
        
        self.handler.charge_refunded(charge)
        
        # Verify emails were sent to owner and admins
        self.assertEqual(mock_send_email.call_count, 3)
    
    @patch("logging.Logger.warning")
    @patch("stripe.Charge.retrieve")
    def test_dispute_created(self, retrieve_charge_mock, log_warning_mock):
        dispute = Mock()
        dispute.id = "dp_123"
        dispute.charge = "ch_123"
        dispute.amount = 5000
        dispute.status = "needs_response"
        dispute.reason = "fraudulent"
        
        charge = Mock()
        charge.customer = self.owner.stripe_customer_id
        retrieve_charge_mock.return_value = charge
        
        self.handler.dispute_created(dispute)
        
        # Verify warning was logged
        log_warning_mock.assert_called_once()
        
        # Verify charge was retrieved
        retrieve_charge_mock.assert_called_once_with(dispute.charge)
    
    @patch("services.task.TaskService.send_email")
    @patch("stripe.Charge.retrieve")
    def test_dispute_created_sends_emails(self, retrieve_charge_mock, mock_send_email):
        # Create admin users
        admin1 = OwnerFactory(email="admin1@example.com")
        admin2 = OwnerFactory(email="admin2@example.com")
        self.owner.admins = [admin1.ownerid, admin2.ownerid]
        self.owner.email = "owner@example.com"
        self.owner.save()
        
        dispute = Mock()
        dispute.id = "dp_123"
        dispute.charge = "ch_123"
        dispute.amount = 5000
        dispute.status = "needs_response"
        dispute.reason = "fraudulent"
        
        charge = Mock()
        charge.customer = self.owner.stripe_customer_id
        retrieve_charge_mock.return_value = charge
        
        self.handler.dispute_created(dispute)
        
        # Verify emails were sent to owner and admins
        self.assertEqual(mock_send_email.call_count, 3)
    
    @patch("logging.Logger.info")
    def test_invoice_updated(self, log_info_mock):
        invoice = Mock()
        invoice.id = "in_123"
        invoice.customer = self.owner.stripe_customer_id
        invoice.status = "open"
        invoice.total = 5000
        
        self.handler.invoice_updated(invoice)
        
        # Verify info was logged
        log_info_mock.assert_called_once()
    
    @patch("services.task.TaskService.send_email")
    def test_invoice_updated_sends_emails_when_open(self, mock_send_email):
        # Create admin users
        admin1 = OwnerFactory(email="admin1@example.com")
        admin2 = OwnerFactory(email="admin2@example.com")
        self.owner.admins = [admin1.ownerid, admin2.ownerid]
        self.owner.email = "owner@example.com"
        self.owner.save()
        
        invoice = Mock()
        invoice.id = "in_123"
        invoice.customer = self.owner.stripe_customer_id
        invoice.status = "open"
        invoice.total = 5000
        
        self.handler.invoice_updated(invoice)
        
        # Verify emails were sent to owner and admins
        self.assertEqual(mock_send_email.call_count, 3)
    
    @patch("services.task.TaskService.send_email")
    def test_invoice_updated_doesnt_send_emails_when_not_open(self, mock_send_email):
        # Create admin users
        admin1 = OwnerFactory(email="admin1@example.com")
        admin2 = OwnerFactory(email="admin2@example.com")
        self.owner.admins = [admin1.ownerid, admin2.ownerid]
        self.owner.email = "owner@example.com"
        self.owner.save()
        
        invoice = Mock()
        invoice.id = "in_123"
        invoice.customer = self.owner.stripe_customer_id
        invoice.status = "paid"
        invoice.total = 5000
        
        self.handler.invoice_updated(invoice)
        
        # Verify no emails were sent since status isn't open
        mock_send_email.assert_not_called()
    
    @patch("logging.Logger.info")
    def test_account_updated(self, log_info_mock):
        account = Mock()
        account.id = "acct_123"
        account.email = "test@example.com"
        
        self.handler.account_updated(account)
        
        # Verify info was logged
        log_info_mock.assert_called_once()
    
    @patch("logging.Logger.info")
    def test_default_event_handler(self, log_info_mock):
        event_object = {"id": "evt_123", "type": "unknown.event"}
        
        self.handler.default_event_handler(event_object)
        
        # Verify info was logged
        log_info_mock.assert_called_once()
    
    @patch("time.sleep")
    @patch("logging.Logger.info")
    def test_simulate_delay(self, log_info_mock, sleep_mock):
        seconds = 5
        
        self.handler.simulate_delay(seconds)
        
        # Verify delay was simulated
        sleep_mock.assert_called_once_with(seconds)
        log_info_mock.assert_called_once()
    
    @patch("shared.plan.service.PlanService")
    @patch("logging.Logger.info")
    def test_revalidate_subscription(self, log_info_mock, plan_service_mock):
        subscription = Mock()
        subscription.id = self.owner.stripe_subscription_id
        subscription.customer = self.owner.stripe_customer_id
        subscription.quantity = 10
        
        self.handler.revalidate_subscription(subscription)
        
        # Verify subscription was revalidated
        log_info_mock.assert_called_once()