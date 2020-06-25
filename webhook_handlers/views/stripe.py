import logging
import stripe
import json

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned

from codecov_auth.models import Owner

from ..constants import StripeHTTPHeaders, StripeWebhookEvents


log = logging.getLogger(__name__)


class StripeWebhookHandler(APIView):
    permission_classes = [AllowAny]

    def invoice_payment_succeeded(self, invoice):
        log.info(f"Setting delinquency status False for stripe customer {invoice.customer}")
        Owner.objects.filter(
            stripe_customer_id=invoice.customer,
            stripe_subscription_id=invoice.subscription.id
        ).update(
            delinquent=False
        )

    def invoice_payment_failed(self, invoice):
        log.info(f"Setting delinquency status True for stripe customer {invoice.customer}")
        Owner.objects.filter(
            stripe_customer_id=invoice.customer,
            stripe_subscription_id=invoice.subscription.id
        ).update(
            delinquent=True
        )

    def customer_subscription_deleted(self, subscription):
        log.info(f"Setting free plan and deactivating repos for stripe customer {subscription.customer}")
        owner = Owner.objects.get(
            stripe_customer_id=subscription.customer,
            stripe_subscription_id=subscription.id
        )

        owner.set_free_plan()
        owner.repository_set.update(
            active=False,
            activated=False
        )

    def post(self, request, *args, **kwargs):
        if settings.STRIPE_ENDPOINT_SECRET is None:
            log.critical("Stripe endpoint secret improperly configured -- webhooks will not be processed.")

        try:
            event = stripe.Webhook.construct_event(
                json.dumps(self.request.data),
                self.request.META.get(StripeHTTPHeaders.SIGNATURE),
                settings.STRIPE_ENDPOINT_SECRET
            )
        except stripe.error.SignatureVerificationError as e:
            log.warn(f"Stripe webhook event received with invalid signature -- {e}")
            return Response("Invalid signature", status=status.HTTP_400_BAD_REQUEST)

        if event.type not in StripeWebhookEvents.subscribed_events:
            log.warning(f"Unsupported Stripe webhook event received -- {event.type}")
            return Response("Unsupported event type", status=204)

        log.info(f"Stripe webhook event received -- {event.type}, customer {event.data.object.customer}")

        # Converts event names of the format X.Y.Z into X_Y_Z, and calls
        # the relevant method in this class
        getattr(self, event.type.replace(".", "_"))(event.data.object)

        return Response(status=status.HTTP_204_NO_CONTENT)
