import time
from unittest.mock import patch

import pytest
import stripe
from django.conf import settings
from freezegun import freeze_time
from pytest import raises
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APIRequestFactory, APITestCase

from codecov_auth.models import Owner
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from plan.constants import PlanName, TrialDaysAmount

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


class StripeWebhookHandlerTests(APITestCase):
    def setUp(self):
        self.owner = OwnerFactory(
            stripe_customer_id="20f0", stripe_subscription_id="3p00"
        )

    def _send_event(self, payload, errorSig=None):
        timestamp = time.time_ns()

        request = APIRequestFactory().post(
            reverse("stripe-webhook"), data=payload, format="json"
        )

        return self.client.post(
            reverse("stripe-webhook"),
            **{
                StripeHTTPHeaders.SIGNATURE: errorSig
                or "t={},v1={}".format(
                    timestamp,
                    stripe.WebhookSignature._compute_signature(
                        "{}.{}".format(timestamp, request.body.decode("utf-8")),
                        settings.STRIPE_ENDPOINT_SECRET,
                    ),
                )
            },
            data=payload,
            format="json",
        )

    def test_invalid_event_signature(self):
        response = self._send_event(
            payload={
                "type": "blah",
                "data": {},
            },
            errorSig="lol",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

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

    def test_customer_subscription_deleted_sets_plan_to_free(self):
        self.owner.plan = "users-inappy"
        self.owner.plan_user_count = 20
        self.owner.save()

        self._send_event(
            payload={
                "type": "customer.subscription.deleted",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id,
                        "plan": {"name": self.owner.plan},
                    }
                },
            }
        )
        self.owner.refresh_from_db()

        assert self.owner.plan == PlanName.BASIC_PLAN_NAME.value
        assert self.owner.plan_user_count == 1
        assert self.owner.plan_activated_users is None
        assert self.owner.stripe_subscription_id is None

    def test_customer_subscription_deleted_deactivates_all_repos(self):
        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.owner, activated=True, active=True)

        assert (
            self.owner.repository_set.filter(activated=True, active=True).count() == 3
        )

        self._send_event(
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

    @patch("logging.Logger.info")
    def test_customer_subscription_deleted_no_customer(self, log_info_mock):
        self.owner.plan = "users-inappy"
        self.owner.plan_user_count = 20
        self.owner.save()

        self._send_event(
            payload={
                "type": "customer.subscription.deleted",
                "data": {
                    "object": {
                        "id": "HUH",
                        "customer": "nah",
                        "plan": {"name": self.owner.plan},
                    }
                },
            }
        )

        log_info_mock.assert_called_with(
            "Customer Subscription Deleted - Couldn't find owner, subscription likely already deleted",
            extra={
                "stripe_subscription_id": "HUH",
                "stripe_customer_id": "nah",
            },
        )

    def test_customer_created_logs_and_doesnt_crash(self):
        self._send_event(
            payload={
                "type": "customer.created",
                "data": {"object": {"id": "FOEKDCDEQ", "email": "test@email.com"}},
            }
        )

    def test_customer_subscription_created_does_nothing_if_no_plan_id(self):
        self.owner.stripe_subscription_id = None
        self.owner.stripe_customer_id = None
        self.owner.save()

        self._send_event(
            payload={
                "type": "customer.subscription.created",
                "data": {
                    "object": {
                        "id": "FOEKDCDEQ",
                        "customer": "sdo050493",
                        "plan": {"id": None},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": 20,
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.stripe_subscription_id is None
        assert self.owner.stripe_customer_id is None

    def test_customer_subscription_created_does_nothing_if_plan_not_paid_user_plan(
        self,
    ):
        self.owner.stripe_subscription_id = None
        self.owner.stripe_customer_id = None
        self.owner.save()

        self._send_event(
            payload={
                "type": "customer.subscription.created",
                "data": {
                    "object": {
                        "id": "FOEKDCDEQ",
                        "customer": "sdo050493",
                        "plan": {"id": "?"},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": 20,
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.stripe_subscription_id is None
        assert self.owner.stripe_customer_id is None

    def test_customer_subscription_created_sets_plan_info(self):
        self.owner.stripe_subscription_id = None
        self.owner.stripe_customer_id = None
        self.owner.save()

        stripe_subscription_id = "FOEKDCDEQ"
        stripe_customer_id = "sdo050493"
        plan_name = "users-pr-inappy"
        quantity = 20

        self._send_event(
            payload={
                "type": "customer.subscription.created",
                "data": {
                    "object": {
                        "id": stripe_subscription_id,
                        "customer": stripe_customer_id,
                        "plan": {"id": "plan_H6P16wij3lUuxg"},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": quantity,
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

    @freeze_time("2023-06-19")
    @patch("plan.service.PlanService.expire_trial_when_upgrading")
    @patch("services.billing.stripe.PaymentMethod.attach")
    @patch("services.billing.stripe.Customer.modify")
    def test_customer_subscription_created_can_trigger_trial_expiration(
        self, c_mock, pm_mock, expire_trial_when_upgrading_mock
    ):
        stripe_subscription_id = "FOEKDCDEQ"
        stripe_customer_id = "sdo050493"
        quantity = 20

        self._send_event(
            payload={
                "type": "customer.subscription.created",
                "data": {
                    "object": {
                        "id": stripe_subscription_id,
                        "customer": stripe_customer_id,
                        "plan": {"id": "plan_H6P16wij3lUuxg"},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": quantity,
                        "default_payment_method": "blabla",
                    }
                },
            }
        )

        expire_trial_when_upgrading_mock.assert_called_once()

    @patch("services.billing.stripe.PaymentMethod.attach")
    @patch("services.billing.stripe.Customer.modify")
    def test_customer_subscription_updated_does_not_change_subscription_if_not_paid_user_plan(
        self, c_mock, pm_mock
    ):
        self.owner.plan = PlanName.BASIC_PLAN_NAME.value
        self.owner.plan_user_count = 0
        self.owner.plan_auto_activate = False
        self.owner.save()

        self._send_event(
            payload={
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id,
                        "plan": {"id": "?"},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": 20,
                        "status": "active",
                        "schedule": None,
                        "default_payment_method": "pm_1LhiRsGlVGuVgOrkQguJXdeV",
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.plan == PlanName.BASIC_PLAN_NAME.value
        assert self.owner.plan_user_count == 0
        assert self.owner.plan_auto_activate == False
        pm_mock.assert_called_once_with(
            "pm_1LhiRsGlVGuVgOrkQguJXdeV", customer=self.owner.stripe_customer_id
        )
        c_mock.assert_called_once_with(
            self.owner.stripe_customer_id,
            invoice_settings={"default_payment_method": "pm_1LhiRsGlVGuVgOrkQguJXdeV"},
        )

    @patch("services.billing.stripe.PaymentMethod.attach")
    @patch("services.billing.stripe.Customer.modify")
    def test_customer_subscription_updated_does_not_change_subscription_if_there_is_a_schedule(
        self, c_mock, pm_mock
    ):
        self.owner.plan = "users-pr-inappy"
        self.owner.plan_user_count = 10
        self.owner.plan_auto_activate = False
        self.owner.save()

        self._send_event(
            payload={
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id,
                        "plan": {"id": "?"},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": 20,
                        "status": "active",
                        "schedule": "sub_sched_1K8xfkGlVGuVgOrkxvroyZdH",
                        "default_payment_method": "pm_1LhiRsGlVGuVgOrkQguJXdeV",
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.plan == "users-pr-inappy"
        assert self.owner.plan_user_count == 10
        assert self.owner.plan_auto_activate == False
        pm_mock.assert_called_once_with(
            "pm_1LhiRsGlVGuVgOrkQguJXdeV", customer=self.owner.stripe_customer_id
        )
        c_mock.assert_called_once_with(
            self.owner.stripe_customer_id,
            invoice_settings={"default_payment_method": "pm_1LhiRsGlVGuVgOrkQguJXdeV"},
        )

    @patch("services.billing.stripe.PaymentMethod.attach")
    @patch("services.billing.stripe.Customer.modify")
    def test_customer_subscription_updated_sets_free_and_deactivates_all_repos_if_incomplete_expired(
        self, c_mock, pm_mock
    ):
        self.owner.plan = "users-pr-inappy"
        self.owner.plan_user_count = 10
        self.owner.plan_auto_activate = False
        self.owner.save()

        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.owner, activated=True, active=True)
        RepositoryFactory(author=self.owner, activated=True, active=True)
        assert self.owner.repository_set.count() == 3

        self._send_event(
            payload={
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id,
                        "plan": {
                            "id": "plan_H6P16wij3lUuxg",
                        },
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": 20,
                        "status": "incomplete_expired",
                        "schedule": None,
                        "default_payment_method": "pm_1LhiRsGlVGuVgOrkQguJXdeV",
                    }
                },
            }
        )
        self.owner.refresh_from_db()

        assert self.owner.plan == PlanName.BASIC_PLAN_NAME.value
        assert self.owner.plan_user_count == 1
        assert self.owner.plan_auto_activate == False
        assert self.owner.stripe_subscription_id is None
        assert (
            self.owner.repository_set.filter(active=True, activated=True).count() == 0
        )
        pm_mock.assert_called_once_with(
            "pm_1LhiRsGlVGuVgOrkQguJXdeV", customer=self.owner.stripe_customer_id
        )
        c_mock.assert_called_once_with(
            self.owner.stripe_customer_id,
            invoice_settings={"default_payment_method": "pm_1LhiRsGlVGuVgOrkQguJXdeV"},
        )

    @patch("services.billing.stripe.PaymentMethod.attach")
    @patch("services.billing.stripe.Customer.modify")
    def test_customer_subscription_updated_sets_fields_on_success(
        self, c_mock, pm_mock
    ):
        self.owner.plan = "users-free"
        self.owner.plan_user_count = 5
        self.owner.plan_auto_activate = False

        plan_name = "users-pr-inappy"
        quantity = 20

        self._send_event(
            payload={
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": self.owner.stripe_subscription_id,
                        "customer": self.owner.stripe_customer_id,
                        "plan": {"id": "plan_H6P16wij3lUuxg"},
                        "metadata": {"obo_organization": self.owner.ownerid},
                        "quantity": quantity,
                        "status": "active",
                        "schedule": None,
                        "default_payment_method": "pm_1LhiRsGlVGuVgOrkQguJXdeV",
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.plan == plan_name
        assert self.owner.plan_user_count == quantity
        assert self.owner.plan_auto_activate == True
        pm_mock.assert_called_once_with(
            "pm_1LhiRsGlVGuVgOrkQguJXdeV", customer=self.owner.stripe_customer_id
        )
        c_mock.assert_called_once_with(
            self.owner.stripe_customer_id,
            invoice_settings={"default_payment_method": "pm_1LhiRsGlVGuVgOrkQguJXdeV"},
        )

    @patch("services.billing.stripe.Subscription.retrieve")
    def test_subscription_schedule_released_updates_owner_with_existing_subscription(
        self, retrieve_subscription_mock
    ):
        self.owner.plan = "users-pr-inappy"
        self.owner.plan_user_count = 10
        self.owner.save()

        self.new_params = {
            "new_plan": "plan_H6P3KZXwmAbqPS",
            "new_id": "plan_H6P3KZXwmAbqPS",
            "new_quantity": 7,
            "subscription_id": None,
        }

        retrieve_subscription_mock.return_value = MockSubscription(
            self.owner, self.new_params
        )

        self._send_event(
            payload={
                "type": "subscription_schedule.released",
                "data": {
                    "object": {
                        "released_subscription": "sub_sched_1K8xfkGlVGuVgOrkxvroyZdH"
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.plan == settings.STRIPE_PLAN_VALS[self.new_params["new_plan"]]
        assert self.owner.plan_user_count == self.new_params["new_quantity"]

    @patch("services.billing.stripe.Subscription.retrieve")
    def test_subscription_schedule_created_logs_a_new_schedule(
        self, retrieve_subscription_mock
    ):
        original_plan = "users-pr-inappy"
        original_quantity = 10
        subscription_id = "sub_1K8xfkGlVGuVgOrkxvroyZdH"
        self.owner.plan = original_plan
        self.owner.plan_user_count = original_quantity
        self.owner.save()

        self.params = {
            "new_plan": "plan_H6P3KZXwmAbqPS",
            "new_quantity": 7,
            "subscription_id": subscription_id,
        }

        retrieve_subscription_mock.return_value = MockSubscription(
            self.owner, self.params
        )

        self._send_event(
            payload={
                "type": "subscription_schedule.created",
                "data": {"object": {"subscription": subscription_id}},
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.plan == original_plan
        assert self.owner.plan_user_count == original_quantity

    @patch("services.billing.stripe.Subscription.retrieve")
    def test_subscription_schedule_updated_logs_changes_to_schedule(
        self, retrieve_subscription_mock
    ):
        original_plan = "users-pr-inappy"
        original_quantity = 10
        subscription_id = "sub_1K8xfkGlVGuVgOrkxvroyZdH"
        new_plan = "plan_H6P3KZXwmAbqPS"
        new_quantity = 7
        self.owner.plan = original_plan
        self.owner.plan_user_count = original_quantity
        self.owner.save()

        self.params = {
            "new_plan": new_plan,
            "new_quantity": new_quantity,
            "subscription_id": subscription_id,
        }

        retrieve_subscription_mock.return_value = MockSubscription(
            self.owner, self.params
        )

        self._send_event(
            payload={
                "type": "subscription_schedule.updated",
                "data": {
                    "object": {
                        "subscription": subscription_id,
                        "phases": [
                            {},
                            {"items": [{"plan": new_plan, "quantity": new_quantity}]},
                        ],
                    }
                },
            }
        )

        self.owner.refresh_from_db()
        assert self.owner.plan == original_plan
        assert self.owner.plan_user_count == original_quantity

    def test_checkout_session_completed_sets_stripe_customer_id(self):
        self.owner.stripe_customer_id = None
        self.owner.save()

        expected_id = "fhjtwoo40"

        self._send_event(
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

    @patch("billing.views.stripe.Subscription.modify")
    def test_customer_update_but_not_payment_method(self, subscription_modify_mock):
        payment_method = "pm_123"
        self._send_event(
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
        self._send_event(
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
