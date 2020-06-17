import stripe
import logging

from django.conf import settings

from utils.config import get_config, MissingConfigException

from codecov_auth.constants import USER_PLAN_REPRESENTATIONS


log = logging.getLogger(__name__)


if settings.STRIPE_API_KEY:
    stripe.api_key = settings.STRIPE_API_KEY
else:
    log.warn("Missing stripe API key configuration -- communication with stripe won't be possible.")


class BillingException(Exception):
    def __init__(self, http_status=None, message=None):
        self.http_status = http_status
        self.message = message


def _stripe_safe(method):
    def catch_and_raise(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except stripe.error.StripeError as e:
            raise BillingException(
                http_status=e.http_status,
                message=e.user_message
            )
    return catch_and_raise


class StripeService:

    @_stripe_safe
    def list_invoices(self, owner, limit=10):
        log.info(f"Fetching invoices from Stripe for ownerid {owner.ownerid}")
        if owner.stripe_customer_id is None:
            log.info("stripe_customer_id is None, not fetching invoices")
            return []
        return stripe.Invoice.list(customer=owner.stripe_customer_id, limit=limit)["data"]

    @_stripe_safe
    def delete_subscription(self, owner):
        if owner.plan not in USER_PLAN_REPRESENTATIONS:
            log.info(f"Downgrade to free plan from legacy plan for owner {owner.ownerid}")
            stripe.Subscription.delete(owner.stripe_subscription_id, prorate=True)
            owner.set_free_plan()
        else:
            log.info(f"Downgrade to free plan from user plan for owner {owner.ownerid}")
            stripe.Subscription.modify(owner.stripe_subscription_id, cancel_at_period_end=True)


class BillingService:
    payment_service = None

    def __init__(self, payment_service=None):
        if payment_service is None:
            self.payment_service = StripeService()
        else:
            self.payment_service = payment_service

    def list_invoices(self, owner, limit=10):
        log.info(f"Fetching invoices for ownerid {owner.ownerid}")
        return self.payment_service.list_invoices(owner, limit)

    def update_plan(self, owner, plan):
        log.info(f"Updating plan for owner {owner.ownerid} to {plan['value']}")
        if plan["value"] == "users-free":
            if owner.stripe_subscription_id is not None:
                self.payment_service.delete_subscription(owner)
            else:
                owner.set_free_plan()
