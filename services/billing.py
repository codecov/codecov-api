import stripe
import logging
from abc import ABC, abstractmethod

from django.conf import settings

from codecov_auth.constants import USER_PLAN_REPRESENTATIONS
from codecov_auth.models import Owner


log = logging.getLogger(__name__)


if settings.STRIPE_API_KEY:
    stripe.api_key = settings.STRIPE_API_KEY
else:
    log.warn("Missing stripe API key configuration -- communication with stripe won't be possible.")


def _log_stripe_error(method):
    def catch_and_raise(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except stripe.error.StripeError as e:
            log.warn(e.user_message)
            raise
    return catch_and_raise


class AbstractPaymentService(ABC):
    @abstractmethod
    def list_invoices(self, owner, limit=10):
        pass

    @abstractmethod
    def delete_subscription(self, owner):
        pass

    @abstractmethod
    def modify_subscription(self, owner, plan):
        pass

    @abstractmethod
    def create_checkout_session(self, owner, plan):
        pass


class StripeService(AbstractPaymentService):

    def __init__(self, requesting_user):
        if not isinstance(requesting_user, Owner):
            raise Exception("StripeService requires requesting_user to be Owner instance")

        self.requesting_user = requesting_user

    def _get_checkout_session_and_subscription_metadata(self, owner):
        return {
            "service": owner.service,
            "obo_organization": owner.ownerid,
            "username": owner.username,
            "obo_name": self.requesting_user.name,
            "obo_email": self.requesting_user.email,
            "obo": self.requesting_user.ownerid
        }

    @_log_stripe_error
    def list_invoices(self, owner, limit=10):
        log.info(f"Fetching invoices from Stripe for ownerid {owner.ownerid}")
        if owner.stripe_customer_id is None:
            log.info("stripe_customer_id is None, not fetching invoices")
            return []
        return stripe.Invoice.list(customer=owner.stripe_customer_id, limit=limit)["data"]

    @_log_stripe_error
    def delete_subscription(self, owner):
        if owner.plan not in USER_PLAN_REPRESENTATIONS:
            log.info(f"Downgrade to free plan from legacy plan for owner {owner.ownerid}")
            stripe.Subscription.delete(owner.stripe_subscription_id, prorate=True)
            owner.set_free_plan()
        else:
            log.info(f"Downgrade to free plan from user plan for owner {owner.ownerid}")
            stripe.Subscription.modify(owner.stripe_subscription_id, cancel_at_period_end=True)

    @_log_stripe_error
    def modify_subscription(self, owner, desired_plan):
        log.info(f"Updating Stripe subscription for owner {owner.ownerid} to {desired_plan['value']}")
        subscription = stripe.Subscription.retrieve(owner.stripe_subscription_id)
        stripe.Subscription.modify(
            owner.stripe_subscription_id,
            cancel_at_period_end=False,
            items=[
                {
                    "id": subscription["items"]["data"][0]["id"],
                    "plan": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                    "quantity": desired_plan["quantity"]
                }
            ],
            metadata=self._get_checkout_session_and_subscription_metadata(owner)
        )

        owner.plan = desired_plan["value"]
        owner.plan_user_count = desired_plan["quantity"]
        owner.save()

        log.info(f"Stripe subscription modified successfully for owner {owner.ownerid}")

    @_log_stripe_error
    def create_checkout_session(self, owner, desired_plan):
        log.info("Creating Stripe Checkout Session for owner: {owner.ownerid}")
        session = stripe.checkout.Session.create(
            billing_address_collection="required",
            payment_method_types=["card"],
            client_reference_id=owner.ownerid,
            customer=owner.stripe_customer_id,
            customer_email=owner.email,
            success_url=settings.CLIENT_PLAN_CHANGE_SUCCESS_URL,
            cancel_url=settings.CLIENT_PLAN_CHANGE_CANCEL_URL,
            subscription_data={
                "items": [{
                    "plan": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                    "quantity": desired_plan["quantity"]
                }],
                "payment_behavior": "allow_incomplete",
                "metadata": self._get_checkout_session_and_subscription_metadata(owner)
            }
        )
        log.info(f"Stripe Checkout Session created successfully for owner {owner.ownerid}")
        return session["id"]


class BillingService:
    payment_service = None

    def __init__(self, payment_service=None, requesting_user=None):
        if payment_service is None:
            self.payment_service = StripeService(requesting_user=requesting_user)
        else:
            self.payment_service = payment_service

        if not issubclass(type(self.payment_service), AbstractPaymentService):
            raise Exception("self.payment_service must subclass AbstractPaymentService!")

    def list_invoices(self, owner, limit=10):
        return self.payment_service.list_invoices(owner, limit)

    def update_plan(self, owner, desired_plan):
        """
        Takes an owner and desired plan, and updates the owner's plan. Depending
        on current state, might create a stripe checkout session and return
        the checkout session's ID, which is a string. Otherwise returns None.
        """
        if desired_plan["value"] == "users-free":
            if owner.stripe_subscription_id is not None:
                self.payment_service.delete_subscription(owner)
            else:
                owner.set_free_plan()
        elif desired_plan["value"] in ("users-inappy", "users-inappm"):
            if owner.stripe_subscription_id is not None:
                self.payment_service.modify_subscription(owner, desired_plan)
            else:
                return self.payment_service.create_checkout_session(owner, desired_plan)
        else:
            log.warn(
                f"Attempted to transition to non-existent or legacy plan: "
                f"owner {owner.ownerid}, plan: {desired_plan}"
            )
