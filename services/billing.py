import stripe
import logging

from django.conf import settings

from utils.config import get_config, MissingConfigException


log = logging.getLogger(__name__)


if settings.STRIPE_API_KEY:
    stripe.api_key = settings.STRIPE_API_KEY
else:
    log.warn("Missing stripe API key configuration -- communication with stripe won't be possible.")


class BillingException(Exception):
    def __init__(self, http_status=None, message=None):
        self.http_status = http_status
        self.message = message


class StripeService:
    def list_invoices(self, owner, limit=10):
        log.info(f"Fetching invoices from stripe for ownerid {owner.ownerid}")
        try:
            return stripe.Invoice.list(customer=owner.stripe_customer_id, limit=limit)["data"]
        except stripe.error.StripeError as e:
            raise BillingException(
                http_status=e.http_status,
                message=e.user_message
            )


class BillingService:
    payment_service = None

    def __init__(self, payment_service=None):
        if payment_service is None:
            self.payment_service = StripeService()
        else:
            self.payment_service = payment_service

    def list_invoices(self, owner, limit=10):
        return self.payment_service.list_invoices(owner, limit)
