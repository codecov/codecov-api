import json
import time
from unittest.mock import patch

import stripe
from django.conf import settings
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIRequestFactory, APITestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory

from ..constants import StripeHTTPHeaders


class StripeWebhookHandlerTests(APITestCase):
    def setUp(self):
        self.owner = OwnerFactory(
            stripe_customer_id="20f0", stripe_subscription_id="3p00"
        )

    def _send_event(self, payload):
        timestamp = time.time_ns()

        request = APIRequestFactory().post(
            reverse("stripe-webhook"), data=payload, format="json"
        )

        return self.client.post(
            reverse("stripe-webhook"),
            **{
                StripeHTTPHeaders.SIGNATURE: "t={},v1={}".format(
                    timestamp,
                    stripe.WebhookSignature._compute_signature(
                        "{}.{}".format(timestamp, request.body.decode("utf-8")),
                        settings.STRIPE_ENDPOINT_SECRET,
                    ),
                )
            },
            data=payload,
            format="json"
        )

    def test_invoice_payment_succeeded_sets_owner_delinquent_false(self):
        self.owner.deliquent = True
        self.owner.save()

        response = self._send_event(
            payload={
                "type": "invoice.payment_succeeded",
                "data": {
                    "object": {
                        "customer": self.owner.stripe_customer_id,
                        "subscription": self.owner.stripe_subscription_id,
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert self.owner.delinquent is False

    @patch("services.segment.SegmentService.account_paid_subscription")
    def test_invoice_payment_succeeded_triggers_segment_event(
        self, segment_paid_sub_mock
    ):
        response = self._send_event(
            payload={
                "type": "invoice.payment_succeeded",
                "data": {
                    "object": {
                        "customer": self.owner.stripe_customer_id,
                        "subscription": self.owner.stripe_subscription_id,
                    }
                },
            }
        )

        segment_paid_sub_mock.assert_called_once_with(
            self.owner.ownerid, {"plan": self.owner.plan}
        )

    def test_invoice_payment_failed_sets_owner_delinquent_true(self):
        self.owner.delinquent = False
        self.owner.save()

        response = self._send_event(
            payload={
                "type": "invoice.payment_failed",
                "data": {
                    "object": {
                        "customer": self.owner.stripe_customer_id,
                        "subscription": self.owner.stripe_subscription_id,
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert self.owner.delinquent is True

    @patch("codecov_auth.models.Owner.set_free_plan")
    def test_customer_subscription_deleted_sets_plan_to_free(self, set_free_plan_mock):
        self.owner.plan = "users-inappy"
        self.owner.plan_user_count = 20
        self.owner.save()

        response = self._send_event(
            payload={
                "type": "customer.subscription.deleted",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id,
                        "plan": {"name": "users-inappm"},
                    }
                },
            }
        )

        set_free_plan_mock.assert_called_once()

    def test_customer_subscription_deleted_deactivates_all_repos(self):
        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.owner, activated=True, active=True)

        assert (
            self.owner.repository_set.filter(activated=True, active=True).count() == 3
        )

        response = self._send_event(
            payload={
                "type": "customer.subscription.deleted",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id,
                        "plan": {"name": "users-inappm"},
                    }
                },
            }
        )

        assert (
            self.owner.repository_set.filter(activated=True, active=True).count() == 0
        )

    @patch("services.segment.SegmentService.account_cancelled_subscription")
    def test_customer_subscription_deleted_triggers_segment(
        self, account_deleted_subscription_mock
    ):
        response = self._send_event(
            payload={
                "type": "customer.subscription.deleted",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id,
                        "plan": {"name": "users-inappm"},
                    }
                },
            }
        )

        account_deleted_subscription_mock.assert_called_once_with(
            self.owner.ownerid, {"plan": "users-inappm"}
        )

    def test_customer_created_logs_and_doesnt_crash(self):
        response = self._send_event(
            payload={
                "type": "customer.created",
                "data": {"object": {"id": "FOEKDCDEQ", "email": "test@email.com"}},
            }
        )

    def test_customer_subscription_created_does_nothing_if_no_plan_id(self):
        self.owner.stripe_subscription_id = None
        self.owner.stripe_customer_id = None
        self.owner.save()

        response = self._send_event(
            payload={
                "type": "customer.subscription.created",
                "data": {
                    "object": {
                        "id": "FOEKDCDEQ",
                        "customer": "sdo050493",
                        "plan": {"id": None, "name": "users-inappy"},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": 20,
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.stripe_subscription_id == None
        assert self.owner.stripe_customer_id == None

    def test_customer_subscription_created_does_nothing_if_plan_not_paid_user_plan(
        self,
    ):
        self.owner.stripe_subscription_id = None
        self.owner.stripe_customer_id = None
        self.owner.save()

        response = self._send_event(
            payload={
                "type": "customer.subscription.created",
                "data": {
                    "object": {
                        "id": "FOEKDCDEQ",
                        "customer": "sdo050493",
                        "plan": {"id": "fieown4", "name": "users-free"},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": 20,
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.stripe_subscription_id == None
        assert self.owner.stripe_customer_id == None

    @patch("services.billing.StripeService.update_payment_method")
    def test_customer_subscription_created_sets_plan_info(self, upm_mock):
        self.owner.stripe_subscription_id = None
        self.owner.stripe_customer_id = None
        self.owner.save()

        stripe_subscription_id = "FOEKDCDEQ"
        stripe_customer_id = "sdo050493"
        plan_name = "users-pr-inappy"
        quantity = 20

        response = self._send_event(
            payload={
                "type": "customer.subscription.created",
                "data": {
                    "object": {
                        "id": stripe_subscription_id,
                        "customer": stripe_customer_id,
                        "plan": {"id": "fieown4", "name": plan_name},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": quantity,
                        "default_payment_method": "pm_abc",
                        "status": "active",
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.stripe_subscription_id == stripe_subscription_id
        assert self.owner.stripe_customer_id == stripe_customer_id
        assert self.owner.plan_user_count == quantity
        assert self.owner.plan_auto_activate is True
        assert self.owner.plan == plan_name
        upm_mock.assert_called_once_with(self.owner, "pm_abc")

    @patch("services.billing.StripeService.update_payment_method")
    @patch("services.segment.SegmentService.trial_started")
    def test_customer_subscription_created_can_trigger_identify_and_trialing_segment_events(
        self, trial_started_mock, _
    ):
        trial_start, trial_end = "ts", "te"
        stripe_subscription_id = "FOEKDCDEQ"
        stripe_customer_id = "sdo050493"
        plan_name = "users-pr-inappy"
        quantity = 20

        response = self._send_event(
            payload={
                "type": "customer.subscription.created",
                "data": {
                    "object": {
                        "id": stripe_subscription_id,
                        "customer": stripe_customer_id,
                        "plan": {"id": "fieown4", "name": plan_name},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": quantity,
                        "status": "trialing",
                        "trial_start": trial_start,
                        "trial_end": trial_end,
                        "default_payment_method": "blabla",
                    }
                },
            }
        )

        trial_started_mock.assert_called_once_with(
            self.owner.ownerid,
            {
                "trial_plan_name": plan_name,
                "trial_plan_user_count": quantity,
                "trial_end_date": trial_end,
                "trial_start_date": trial_start,
            },
        )

    def test_customer_subscription_updated_does_nothing_if_not_paid_user_plan(self):
        self.owner.plan = None
        self.owner.plan_user_count = 0
        self.owner.plan_auto_activate = False
        self.owner.save()

        response = self._send_event(
            payload={
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id,
                        "plan": {"id": "fieown4", "name": "users-free"},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": 20,
                        "status": "active",
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.plan == None
        assert self.owner.plan_user_count == 0
        assert self.owner.plan_auto_activate == False

    @patch("codecov_auth.models.Owner.set_free_plan")
    def test_customer_subscription_updated_sets_free_and_deactivates_all_repos_if_incomplete_expired(
        self, set_free_plan_mock
    ):
        self.owner.plan = "users-pr-inappy"
        self.owner.plan_user_count = 10
        self.owner.plan_auto_activate = False
        self.owner.save()

        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.owner, activated=True, active=True)
        assert self.owner.repository_set.count() == 3

        response = self._send_event(
            payload={
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id,
                        "plan": {"id": "fieown4", "name": "users-pr-inappy"},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": 20,
                        "status": "incomplete_expired",
                    }
                },
            }
        )

        set_free_plan_mock.assert_called_once()

        assert (
            self.owner.repository_set.filter(active=True, activated=True).count() == 0
        )

    def test_customer_subscription_updated_sets_fields_on_success(self):
        self.owner.plan = "users-free"
        self.owner.plan_user_count = 5
        self.owner.plan_auto_activate = False

        plan_name = "users-pr-inappy"
        quantity = 20

        response = self._send_event(
            payload={
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id,
                        "plan": {"id": "fieown4", "name": plan_name},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": quantity,
                        "status": "active",
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.plan == plan_name
        assert self.owner.plan_user_count == quantity
        assert self.owner.plan_auto_activate == True

    @patch("services.segment.SegmentService.trial_ended")
    def test_customer_subscription_updated_triggers_segment_event_on_trial_end(
        self, trial_ended_mock
    ):
        trial_start, trial_end = "ts", "te"
        response = self._send_event(
            payload={
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id,
                        "plan": {"id": "fieown4", "name": "users-pr-inappm"},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": 10,
                        "status": "active",
                        "trial_start": trial_start,
                        "trial_end": trial_end,
                    },
                    "previous_attributes": {"status": "trialing"},
                },
            }
        )

        trial_ended_mock.assert_called_once_with(
            self.owner.ownerid,
            {
                "trial_plan_name": "users-pr-inappm",
                "trial_plan_user_count": 10,
                "trial_end_date": trial_end,
                "trial_start_date": trial_start,
            },
        )

    def test_checkout_session_completed_sets_stripe_customer_id(self):
        self.owner.stripe_customer_id = None
        self.owner.save()

        expected_id = "fhjtwoo40"

        response = self._send_event(
            payload={
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "customer": expected_id,
                        "client_reference_id": str(self.owner.ownerid),
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.stripe_customer_id == expected_id

    @patch("services.segment.SegmentService.account_completed_checkout")
    def test_checkout_session_completed_triggers_segment_event(
        self, account_co_completed_mock
    ):
        plan = "users-pr-inappy"
        response = self._send_event(
            payload={
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "customer": "fhjtwoo40",
                        "client_reference_id": str(self.owner.ownerid),
                        "display_items": [{"plan": {"name": plan}}],
                    }
                },
            }
        )

        account_co_completed_mock.assert_called_once_with(
            self.owner.ownerid, {"plan": plan, "userid_type": "org"}
        )

    @patch("billing.views.stripe.Subscription.modify")
    def test_customer_update_but_not_payment_method(self, subscription_modify_mock):
        payment_method = "pm_123"
        response = self._send_event(
            payload={
                "type": "customer.updated",
                "data": {
                    "object": {
                        "invoice_settings": {"default_payment_method": payment_method},
                        "subscriptions": {
                            "data": [{"default_payment_method": payment_method}]
                        },
                    }
                },
            }
        )

        subscription_modify_mock.assert_not_called()

    @patch("billing.views.stripe.Subscription.modify")
    def test_customer_update_payment_method(self, subscription_modify_mock):
        payment_method = "pm_123"
        old_payment_method = "pm_321"
        response = self._send_event(
            payload={
                "type": "customer.updated",
                "data": {
                    "object": {
                        "id": "cus_123",
                        "invoice_settings": {"default_payment_method": payment_method},
                        "subscriptions": {
                            "data": [
                                {
                                    "id": "sub_123",
                                    "default_payment_method": old_payment_method,
                                }
                            ]
                        },
                    }
                },
            }
        )

        subscription_modify_mock.assert_called_once_with(
            "sub_123", default_payment_method=payment_method
        )
