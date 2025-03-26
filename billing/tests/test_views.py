import time
from datetime import datetime
from unittest.mock import Mock, call, patch

import stripe
from django.conf import settings
from freezegun import freeze_time
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIRequestFactory, APITestCase
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory
from shared.plan.constants import DEFAULT_FREE_PLAN, PlanName

from billing.helpers import mock_all_plans_and_tiers
from billing.views import StripeWebhookHandler
from codecov_auth.models import Plan

from ..constants import StripeHTTPHeaders


class MockSubscriptionPlan(object):
    def __init__(self, params):
        self.id = params["new_plan"]


class MockSubscription(object):
    def __init__(self, owner, params):
        self.metadata = {"obo_organization": owner.ownerid, "obo": 15}
        self.plan = MockSubscriptionPlan(params)
        self.quantity = params["new_quantity"]
        self.customer = "cus_123"
        self.id = params["subscription_id"]
        self.items = {
            "data": [
                {
                    "quantity": params["new_quantity"],
                    "plan": {"id": params["new_plan"]},
                }
            ]
        }

    def __getitem__(self, key):
        return getattr(self, key)


class MockCard(object):
    def __init__(self):
        self.brand = "visa"
        self.last4 = "1234"

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


class MockPaymentMethod(object):
    def __init__(self, noCard=False):
        if noCard:
            self.card = None
            return

        self.card = MockCard()

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


class MockPaymentIntent(object):
    def __init__(self, noCard=False):
        self.payment_method = MockPaymentMethod(noCard)
        self.status = "succeeded"

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)


class StripeWebhookHandlerTests(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        mock_all_plans_and_tiers()

    def setUp(self):
        self.owner = OwnerFactory(
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
        )

    # Creates a second owner that shares billing details with self.owner.
    # This is used to test the case where owners are manually set to share a
    # subscription in Stripe.
    def add_second_owner(self):
        self.other_owner = OwnerFactory(
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
        )
