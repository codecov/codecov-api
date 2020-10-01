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
from codecov_auth.constants import PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS

from ..constants import StripeHTTPHeaders, StripeWebhookEvents


log = logging.getLogger(__name__)


class StripeWebhookHandler(APIView):
    permission_classes = [AllowAny]

    def _log_updated(self, updated):
        if updated >= 1:
            log.warning(f"Could not find customer")
        else:
            log.info(f"Successfully updated customer info")

    def invoice_payment_succeeded(self, invoice):
        log.info(
            f"Setting delinquency status False for stripe customer {invoice.customer}"
        )
        updated = Owner.objects.filter(
            stripe_customer_id=invoice.customer,
            stripe_subscription_id=invoice.subscription,
        ).update(delinquent=False)
        self._log_updated(updated)

    def invoice_payment_failed(self, invoice):
        log.info(
            f"Setting delinquency status True for stripe customer {invoice.customer}"
        )
        updated = Owner.objects.filter(
            stripe_customer_id=invoice.customer,
            stripe_subscription_id=invoice.subscription,
        ).update(delinquent=True)
        self._log_updated(updated)

    def customer_subscription_deleted(self, subscription):
        log.info(
            f"Setting free plan and deactivating repos for stripe customer {subscription.customer}"
        )
        owner = Owner.objects.get(
            stripe_customer_id=subscription.customer,
            stripe_subscription_id=subscription.id,
        )

        owner.set_free_plan()
        owner.repository_set.update(active=False, activated=False)
        self._log_updated(1)

    def customer_created(self, customer):
        # Based on what stripe doesn't gives us (an ownerid!)
        # in this event we cannot reliably create a customer,
        # so we're just logging that we created the event and
        # relying on customer.subscription.created to handle sub creation
        log.info(
            f"Customer created with stripe_customer_id: {customer.id} & email: {customer.email}"
        )

    def customer_subscription_created(self, subscription):
        if not subscription.plan.id:
            log.warning("Subscription created missing plan id, exiting")
            return

        if subscription.plan.name not in PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS:
            log.warning(
                f"Subscription creation requested for invalid plan "
                f"'{subscription.plan.name}' -- doing nothing"
            )
            return

        log.info(
            f"Subscription created for customer {subscription.customer} "
            f"with -- plan: {subscription.plan.name}, quantity {subscription.quantity}"
        )
        updated = Owner.objects.filter(
            ownerid=subscription.metadata.obo_organization
        ).update(
            plan=subscription.plan.name,
            plan_user_count=subscription.quantity,
            plan_auto_activate=True,
            stripe_subscription_id=subscription.id,
            stripe_customer_id=subscription.customer,
        )
        self._log_updated(updated)

    def customer_subscription_updated(self, subscription):
        if subscription.status == "incomplete_expired":
            log.info(
                f"Subscription {subscription.id} updated with status change "
                f"to 'incomplete_expired' -- cancelling to free"
            )
            owner = Owner.objects.get(
                stripe_subscription_id=subscription.id,
                stripe_customer_id=subscription.customer,
            )
            owner.set_free_plan()
            owner.repository_set.update(active=False, activated=False)
            return
        if subscription.plan.name not in PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS:
            log.warning(
                f"Subscription update requested with invalid plan "
                f"{subscription.plan.name} -- doing nothing "
            )
            return

        log.info(
            f"Subscription {subscription.id} updated with -- "
            f"plan: {subscription.plan.name}, quantity: {subscription.quantity}"
        )
        updated = Owner.objects.filter(
            stripe_subscription_id=subscription.id,
            stripe_customer_id=subscription.customer,
        ).update(
            plan=subscription.plan.name,
            plan_user_count=subscription.quantity,
            plan_auto_activate=True,
        )
        self._log_updated(updated)

    def checkout_session_completed(self, checkout_session):
        log.info(
            f"Checkout session completed for customer -- ownerid: "
            f"{checkout_session.client_reference_id}"
        )
        updated = Owner.objects.filter(
            ownerid=checkout_session.client_reference_id
        ).update(stripe_customer_id=checkout_session.customer)
        self._log_updated(updated)

    def post(self, request, *args, **kwargs):
        if settings.STRIPE_ENDPOINT_SECRET is None:
            log.critical(
                "Stripe endpoint secret improperly configured -- webhooks will not be processed."
            )

        try:
            event = stripe.Webhook.construct_event(
                self.request.body,
                self.request.META.get(StripeHTTPHeaders.SIGNATURE),
                settings.STRIPE_ENDPOINT_SECRET,
            )
        except stripe.error.SignatureVerificationError as e:
            log.warning(f"Stripe webhook event received with invalid signature -- {e}")
            return Response("Invalid signature", status=status.HTTP_400_BAD_REQUEST)

        if event.type not in StripeWebhookEvents.subscribed_events:
            log.warning(f"Unsupported Stripe webhook event received -- {event.type}")
            return Response("Unsupported event type", status=204)

        log.info(f"Stripe webhook event received -- {event.type}")

        # Converts event names of the format X.Y.Z into X_Y_Z, and calls
        # the relevant method in this class
        getattr(self, event.type.replace(".", "_"))(event.data.object)

        return Response(status=status.HTTP_204_NO_CONTENT)
