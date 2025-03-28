from unittest.mock import Mock, patch

from django.test import TestCase

from billing.constants import DEFAULT_FREE_PLAN
from billing.models import Plan
from billing.views import StripeWebhookHandler
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory


class TestSubscriptionHandlers(TestCase):
    def setUp(self):
        self.handler = StripeWebhookHandler()
        self.owner = OwnerFactory(
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
            plan="users-pr-inappy",
            plan_user_count=10,
            plan_auto_activate=True
        )

    @patch("billing.views.Owner.objects.filter")
    def test_customer_subscription_deleted_sets_free_plan(self, mock_filter):
        # Setup mock owners
        mock_owners = Mock()
        mock_filter.return_value = mock_owners

        # Create mock subscription
        mock_subscription = Mock()
        mock_subscription.id = self.owner.stripe_subscription_id
        mock_subscription.customer = self.owner.stripe_customer_id
        mock_subscription.plan = {"name": self.owner.plan}
        mock_subscription.status = "active"

        # Call the handler method
        self.handler.customer_subscription_deleted(mock_subscription)

        # Verify owners were updated correctly
        mock_owners.update.assert_called_with(
            plan=DEFAULT_FREE_PLAN,
            plan_user_count=1,
            plan_activated_users=None,
            stripe_subscription_id=None
        )

    @patch("billing.views.StripeWebhookHandler._has_unverified_initial_payment_method")
    @patch("billing.views.Owner.objects.get")
    @patch("billing.views.PlanService")
    def test_customer_subscription_created_sets_subscription_ids(
        self, mock_plan_service, mock_get, mock_has_unverified
    ):
        # Mock owner instance and plan service
        mock_owner = Mock()
        mock_get.return_value = mock_owner
        mock_plan_service_instance = Mock()
        mock_plan_service.return_value = mock_plan_service_instance
        mock_has_unverified.return_value = False

        # Create mock subscription with metadata
        mock_subscription = Mock()
        mock_subscription.id = "new_sub_123"
        mock_subscription.customer = "new_cus_123"
        mock_subscription.plan.id = "plan_pro_yearly"
        mock_subscription.quantity = 5
        mock_subscription.metadata.get.return_value = self.owner.ownerid

        # Call the handler method
        self.handler.customer_subscription_created(mock_subscription)

        # Verify owner was retrieved and updated correctly
        mock_get.assert_called_with(ownerid=self.owner.ownerid)
        self.assertEqual(mock_owner.stripe_subscription_id, "new_sub_123")
        self.assertEqual(mock_owner.stripe_customer_id, "new_cus_123")
        mock_owner.save.assert_called_once()

        # Verify plan was updated
        mock_plan_service.assert_called_with(current_org=mock_owner)
        mock_plan_service_instance.expire_trial_when_upgrading.assert_called_once()
        mock_plan_service_instance.update_plan.assert_called_once()

    @patch("billing.views.StripeWebhookHandler._has_unverified_initial_payment_method")
    @patch("billing.views.Owner.objects.get")
    @patch("billing.views.PlanService")
    def test_customer_subscription_created_early_returns_if_unverified(
        self, mock_plan_service, mock_get, mock_has_unverified
    ):
        # Mock owner instance and unverified payment method
        mock_owner = Mock()
        mock_get.return_value = mock_owner
        mock_has_unverified.return_value = True

        # Create mock subscription with metadata
        mock_subscription = Mock()
        mock_subscription.id = "new_sub_123"
        mock_subscription.customer = "new_cus_123"
        mock_subscription.plan.id = "plan_pro_yearly"
        mock_subscription.metadata.get.return_value = self.owner.ownerid

        # Call the handler method
        self.handler.customer_subscription_created(mock_subscription)

        # Verify owner was updated but plan was not
        mock_get.assert_called_with(ownerid=self.owner.ownerid)
        self.assertEqual(mock_owner.stripe_subscription_id, "new_sub_123")
        self.assertEqual(mock_owner.stripe_customer_id, "new_cus_123")
        mock_owner.save.assert_called_once()

        # Verify plan service was not used to update plan
        mock_plan_service_instance = mock_plan_service.return_value
        mock_plan_service_instance.update_plan.assert_not_called()

    @patch("billing.views.stripe.Invoice.retrieve")
    def test_has_unverified_initial_payment_method(self, mock_invoice_retrieve):
        # Mock subscription and payment intent requiring action
        mock_subscription = Mock()
        mock_subscription.latest_invoice = "inv_123"

        mock_invoice = Mock()
        mock_invoice.payment_intent = "pi_123"
        mock_invoice_retrieve.return_value = mock_invoice

        mock_payment_intent = Mock()
        mock_payment_intent.status = "requires_action"
        mock_payment_intent.next_action = {"type": "verify_with_microdeposits"}

        with patch("billing.views.stripe.PaymentIntent.retrieve", return_value=mock_payment_intent):
            result = self.handler._has_unverified_initial_payment_method(mock_subscription)

        self.assertTrue(result)
        mock_invoice_retrieve.assert_called_once_with("inv_123")

    @patch("billing.views.stripe.Invoice.retrieve")
    def test_has_unverified_initial_payment_method_returns_false_when_succeeded(self, mock_invoice_retrieve):
        # Mock subscription and payment intent that succeeded
        mock_subscription = Mock()
        mock_subscription.latest_invoice = "inv_123"

        mock_invoice = Mock()
        mock_invoice.payment_intent = "pi_123"
        mock_invoice_retrieve.return_value = mock_invoice

        mock_payment_intent = Mock()
        mock_payment_intent.status = "succeeded"

        with patch("billing.views.stripe.PaymentIntent.retrieve", return_value=mock_payment_intent):
            result = self.handler._has_unverified_initial_payment_method(mock_subscription)

        self.assertFalse(result)
        mock_invoice_retrieve.assert_called_once_with("inv_123")

    @patch("billing.views.Owner.objects.filter")
    @patch("billing.views.Repository.objects.filter")
    def test_customer_subscription_deleted_deactivates_repositories(
        self, mock_repo_filter, mock_owner_filter
    ):
        # Create mock repositories
        mock_repos = Mock()
        mock_repo_filter.return_value = mock_repos

        # Setup mock owners
        mock_owners = Mock()
        mock_owner_filter.return_value = mock_owners
        mock_owners.__iter__.return_value = [self.owner]

        # Create test repositories
        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.owner, activated=True, active=True)

        # Create mock subscription
        mock_subscription = Mock()
        mock_subscription.id = self.owner.stripe_subscription_id
        mock_subscription.customer = self.owner.stripe_customer_id
        mock_subscription.plan = {"name": self.owner.plan}
        mock_subscription.status = "active"

        # Call the handler method
        self.handler.customer_subscription_deleted(mock_subscription)

        # Verify repositories were deactivated
        mock_repo_filter.assert_called_with(author=self.owner)
        mock_repos.update.assert_called_with(activated=False, active=False)
