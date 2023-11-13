import logging

import stripe
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from codecov_auth.models import Owner
from plan.constants import PAID_PLANS
from plan.service import PlanService
from services.billing import BillingService

from .constants import StripeHTTPHeaders, StripeWebhookEvents

if settings.STRIPE_API_KEY:
    stripe.api_key = settings.STRIPE_API_KEY

log = logging.getLogger(__name__)


class StripeWebhookHandler(APIView):
    permission_classes = [AllowAny]

    def _log_updated(self, updated):
        if updated >= 1:
            log.info(f"Successfully updated info for {updated} customer(s)")
        else:
            log.warning(f"Could not find customer")

    def invoice_payment_succeeded(self, invoice):
        log.info(
            "Setting delinquency status False",
            extra=dict(
                stripe_customer_id=invoice.customer,
                stripe_subscription_id=invoice.subscription,
            ),
        )
        owner = Owner.objects.get(
            stripe_customer_id=invoice.customer,
            stripe_subscription_id=invoice.subscription,
        )

        owner.delinquent = False
        owner.save()

        self._log_updated(1)

    def invoice_payment_failed(self, invoice):
        log.info(
            "Setting delinquency status True",
            extra=dict(
                stripe_customer_id=invoice.customer,
                stripe_subscription_id=invoice.subscription,
            ),
        )
        updated = Owner.objects.filter(
            stripe_customer_id=invoice.customer,
            stripe_subscription_id=invoice.subscription,
        ).update(delinquent=True)
        self._log_updated(updated)

    def customer_subscription_deleted(self, subscription):
        log.info(
            "Setting free plan and deactivating repos for stripe customer",
            extra=dict(
                stripe_subscription_id=subscription.id,
                stripe_customer_id=subscription.customer,
            ),
        )
        owner: Owner = Owner.objects.get(
            stripe_customer_id=subscription.customer,
            stripe_subscription_id=subscription.id,
        )
        plan_service = PlanService(current_org=owner)
        plan_service.set_default_plan_data()
        owner.repository_set.update(active=False, activated=False)

        self._log_updated(1)

    def subscription_schedule_created(self, schedule):
        subscription = stripe.Subscription.retrieve(schedule["subscription"])
        log.info(
            f"Schedule created for customer "
            f"with -- plan: {subscription.plan.name}, quantity {subscription.quantity}",
            extra=dict(
                stripe_customer_id=subscription.customer,
                stripe_subscription_id=subscription.id,
                ownerid=subscription.metadata.obo_organization,
            ),
        )

    def subscription_schedule_updated(self, schedule):
        if schedule["subscription"]:
            subscription = stripe.Subscription.retrieve(schedule["subscription"])
            scheduled_phase = schedule["phases"][1]
            scheduled_plan = scheduled_phase["plans"][0]
            plan_id = scheduled_plan["plan"]
            stripe_plan_dict = settings.STRIPE_PLAN_IDS
            plan_name = list(stripe_plan_dict.keys())[
                list(stripe_plan_dict.values()).index(plan_id)
            ]
            quantity = scheduled_plan["quantity"]
            log.info(
                f"Schedule updated for customer "
                f"with -- plan: {plan_name}, quantity {quantity}",
                extra=dict(
                    stripe_customer_id=subscription.customer,
                    stripe_subscription_id=subscription.id,
                    ownerid=subscription.metadata.obo_organization,
                ),
            )

    def subscription_schedule_released(self, schedule):

        subscription = stripe.Subscription.retrieve(schedule["released_subscription"])
        owner = Owner.objects.get(ownerid=subscription.metadata.obo_organization)
        requesting_user_id = subscription.metadata.obo
        plan_service = PlanService(current_org=owner)

        plan_service = PlanService(current_org=owner)
        plan_service.update_plan(
            name=subscription.plan.name, user_count=subscription.quantity
        )

        log.info(
            f"Stripe subscription modified successfully for owner {owner.ownerid} by user #{requesting_user_id}",
            extra=dict(ownerid=owner.ownerid, requesting_user_id=requesting_user_id),
        )

    def customer_created(self, customer):
        # Based on what stripe doesn't gives us (an ownerid!)
        # in this event we cannot reliably create a customer,
        # so we're just logging that we created the event and
        # relying on customer.subscription.created to handle sub creation
        log.info("Customer created", extra=dict(stripe_customer_id=customer.id))

    def customer_subscription_created(self, subscription):
        if not subscription.plan.id:
            log.warning(
                "Subscription created missing plan id, exiting",
                extra=dict(
                    stripe_customer_id=subscription.customer,
                    ownerid=subscription.metadata.obo_organization,
                ),
            )
            return

        if subscription.plan.name not in PAID_PLANS:
            log.warning(
                f"Subscription creation requested for invalid plan "
                f"'{subscription.plan.name}' -- doing nothing",
                extra=dict(
                    stripe_customer_id=subscription.customer,
                    ownerid=subscription.metadata.obo_organization,
                ),
            )
            return

        log.info(
            f"Subscription created for customer "
            f"with -- plan: {subscription.plan.name}, quantity {subscription.quantity}",
            extra=dict(
                stripe_customer_id=subscription.customer,
                stripe_subscription_id=subscription.id,
                ownerid=subscription.metadata.obo_organization,
            ),
        )
        owner = Owner.objects.get(ownerid=subscription.metadata.obo_organization)
        owner.stripe_subscription_id = subscription.id
        owner.stripe_customer_id = subscription.customer
        owner.save()

        plan_service = PlanService(current_org=owner)
        plan_service.expire_trial_when_upgrading()
        plan_service.update_plan(
            name=subscription.plan.name, user_count=subscription.quantity
        )

        self._log_updated(1)

    def customer_subscription_updated(self, subscription):
        owner: Owner = Owner.objects.get(
            stripe_subscription_id=subscription.id,
            stripe_customer_id=subscription.customer,
        )

        # Properly attach the payment method on the customer
        # This hook will be called after a checkout session completes, updating the subscription created
        # with it
        default_payment_method = subscription.default_payment_method
        if default_payment_method:
            billing = BillingService(requesting_user=owner)
            billing.update_payment_method(owner, default_payment_method)

        subscription_schedule_id = subscription.schedule
        plan_service = PlanService(current_org=owner)

        # Only update if there isn't a scheduled subscription
        if not subscription_schedule_id:
            if subscription.status == "incomplete_expired":
                log.info(
                    f"Subscription updated with status change "
                    f"to 'incomplete_expired' -- cancelling to free",
                    extra=dict(stripe_subscription_id=subscription.id),
                )
                plan_service.set_default_plan_data()
                # TODO: think of how to create services for different objects/classes to delegate responsibilities that are not
                # from the owner
                owner.repository_set.update(active=False, activated=False)
                return
            # TODO: we can delete this if statement if we confirm there aren't any PAID_PLANS out there
            if subscription.plan.name not in PAID_PLANS:
                log.warning(
                    f"Subscription update requested with invalid plan "
                    f"{subscription.plan.name} -- doing nothing",
                    extra=dict(stripe_subscription_id=subscription.id),
                )
                return

            log.info(
                f"Subscription updated with -- "
                f"plan: {subscription.plan.name}, quantity: {subscription.quantity}",
                extra=dict(stripe_subscription_id=subscription.id),
            )

            plan_service.update_plan(
                name=subscription.plan.name, user_count=subscription.quantity
            )
            log.info("Successfully updated info for 1 customer")

    def customer_updated(self, customer):
        new_default_payment_method = customer["invoice_settings"][
            "default_payment_method"
        ]
        for subscription in customer.get("subscriptions", {}).get("data", []):
            if new_default_payment_method == subscription["default_payment_method"]:
                continue
            log.info(
                "Customer updated their payment method, updating the subscription payment as well",
                extra=dict(
                    customer_id=customer["id"], subscription_id=subscription["id"]
                ),
            )
            stripe.Subscription.modify(
                subscription["id"], default_payment_method=new_default_payment_method
            )

    def checkout_session_completed(self, checkout_session):
        log.info(
            "Checkout session completed",
            extra=dict(ownerid=checkout_session.client_reference_id),
        )
        owner = Owner.objects.get(ownerid=checkout_session.client_reference_id)
        owner.stripe_customer_id = checkout_session.customer
        owner.save()

        # Segment
        segment_checkout_session_details = {"plan": None, "userid_type": "org"}
        try:
            segment_checkout_session_details["plan"] = checkout_session.display_items[
                0
            ]["plan"]["name"]
        except:
            log.warning(
                "Could not find plan in checkout.session.completed event",
                extra=dict(ownerid=checkout_session.client_reference_id),
            )

        self._log_updated(1)

    def post(self, request, *args, **kwargs):
        if settings.STRIPE_ENDPOINT_SECRET is None:
            log.critical(
                "Stripe endpoint secret improperly configured -- webhooks will not be processed."
            )
        try:
            self.event = stripe.Webhook.construct_event(
                self.request.body,
                self.request.META.get(StripeHTTPHeaders.SIGNATURE),
                settings.STRIPE_ENDPOINT_SECRET,
            )
        except stripe.error.SignatureVerificationError as e:
            log.warning(f"Stripe webhook event received with invalid signature -- {e}")
            return Response("Invalid signature", status=status.HTTP_400_BAD_REQUEST)
        if self.event.type not in StripeWebhookEvents.subscribed_events:
            log.warning(
                f"Unsupported Stripe webhook event received, exiting",
                extra=dict(stripe_webhook_event=self.event.type),
            )
            return Response("Unsupported event type", status=204)

        log.info(
            f"Stripe webhook event received",
            extra=dict(stripe_webhook_event=self.event.type),
        )

        # Converts event names of the format X.Y.Z into X_Y_Z, and calls
        # the relevant method in this class
        getattr(self, self.event.type.replace(".", "_"))(self.event.data.object)

        return Response(status=status.HTTP_204_NO_CONTENT)
