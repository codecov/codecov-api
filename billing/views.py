import logging

import stripe
from django.conf import settings
from django.db.models import QuerySet
from django.http import HttpRequest
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from codecov_auth.models import Owner
from plan.service import PlanService

from .constants import StripeHTTPHeaders, StripeWebhookEvents

if settings.STRIPE_API_KEY:
    stripe.api_key = settings.STRIPE_API_KEY
    stripe.api_version = "2024-04-10"

log = logging.getLogger(__name__)


class StripeWebhookHandler(APIView):
    permission_classes = [AllowAny]

    def _log_updated(self, updated: int) -> None:
        if updated >= 1:
            log.info(f"Successfully updated info for {updated} customer(s)")
        else:
            log.warning("Could not find customer")

    def invoice_payment_succeeded(self, invoice: stripe.Invoice) -> None:
        log.info(
            "Invoice Payment Succeeded - Setting delinquency status False",
            extra=dict(
                stripe_customer_id=invoice.customer,
                stripe_subscription_id=invoice.subscription,
            ),
        )
        updated: int = Owner.objects.filter(
            stripe_customer_id=invoice.customer,
            stripe_subscription_id=invoice.subscription,
        ).update(delinquent=False)

        self._log_updated(updated)

    def invoice_payment_failed(self, invoice: stripe.Invoice) -> None:
        log.info(
            "Invoice Payment Failed - Setting Delinquency status True",
            extra=dict(
                stripe_customer_id=invoice.customer,
                stripe_subscription_id=invoice.subscription,
            ),
        )
        updated: int = Owner.objects.filter(
            stripe_customer_id=invoice.customer,
            stripe_subscription_id=invoice.subscription,
        ).update(delinquent=True)
        self._log_updated(updated)

    def customer_subscription_deleted(self, subscription: stripe.Subscription) -> None:
        log.info(
            "Customer Subscription Deleted - Setting free plan and deactivating repos for stripe customer",
            extra=dict(
                stripe_subscription_id=subscription.id,
                stripe_customer_id=subscription.customer,
            ),
        )
        owners: QuerySet[Owner] = Owner.objects.filter(
            stripe_customer_id=subscription.customer,
            stripe_subscription_id=subscription.id,
        )
        if not owners.exists():
            log.info(
                "Customer Subscription Deleted - Couldn't find owner, subscription likely already deleted",
                extra=dict(
                    stripe_subscription_id=subscription.id,
                    stripe_customer_id=subscription.customer,
                ),
            )
            return

        for owner in owners:
            plan_service = PlanService(owner)
            plan_service.set_default_plan_data()
            owner.repository_set.update(active=False, activated=False)

        self._log_updated(owners.count())

    def subscription_schedule_created(
        self, schedule: stripe.SubscriptionSchedule
    ) -> None:
        subscription = stripe.Subscription.retrieve(schedule["subscription"])
        sub_item_plan_id = subscription.plan.id
        plan_name = settings.STRIPE_PLAN_VALS[sub_item_plan_id]
        log.info(
            "Schedule created for customer",
            extra=dict(
                stripe_customer_id=subscription.customer,
                stripe_subscription_id=subscription.id,
                ownerid=subscription.metadata.get("obo_organization"),
                plan=plan_name,
                quantity=subscription.quantity,
            ),
        )

    def subscription_schedule_updated(
        self, schedule: stripe.SubscriptionSchedule
    ) -> None:
        if schedule["subscription"]:
            subscription = stripe.Subscription.retrieve(schedule["subscription"])
            scheduled_phase = schedule["phases"][-1]
            scheduled_plan = scheduled_phase["items"][0]
            plan_id = scheduled_plan["plan"]
            stripe_plan_dict = settings.STRIPE_PLAN_IDS
            plan_name = list(stripe_plan_dict.keys())[
                list(stripe_plan_dict.values()).index(plan_id)
            ]
            quantity = scheduled_plan["quantity"]
            log.info(
                "Schedule updated for customer",
                extra=dict(
                    stripe_customer_id=subscription.customer,
                    stripe_subscription_id=subscription.id,
                    ownerid=subscription.metadata.get("obo_organization"),
                    plan=plan_name,
                    quantity=quantity,
                ),
            )

    def subscription_schedule_released(
        self, schedule: stripe.SubscriptionSchedule
    ) -> None:
        subscription = stripe.Subscription.retrieve(schedule["released_subscription"])
        print(schedule)
        owners: QuerySet[Owner] = Owner.objects.filter(
            stripe_subscription_id=subscription.id,
            stripe_customer_id=subscription.customer,
        )
        if not owners.exists():
            log.error(
                "Subscription schedule released requested with invalid subscription",
                extra=dict(
                    stripe_subscription_id=subscription.id,
                    stripe_customer_id=subscription.customer,
                    plan_id=subscription.plan.id,
                ),
            )
            return

        plan_services = [PlanService(current_org=owner) for owner in owners]

        requesting_user_id = subscription.metadata.get("obo")
        sub_item_plan_id = subscription.plan.id
        plan_name = settings.STRIPE_PLAN_VALS[sub_item_plan_id]
        for service in plan_services:
            service.update_plan(name=plan_name, user_count=subscription.quantity)

        log.info(
            "Successfully updated customer plan info",
            extra=dict(
                stripe_subscription_id=subscription.id,
                stripe_customer_id=subscription.customer,
                plan=plan_name,
                quantity=subscription.quantity,
                owners=[owner.ownerid for owner in owners],
                requesting_user_id=requesting_user_id,
            ),
        )

    def customer_created(self, customer: stripe.Customer) -> None:
        # Based on what stripe doesn't gives us (an ownerid!)
        # in this event we cannot reliably create a customer,
        # so we're just logging that we created the event and
        # relying on customer.subscription.created to handle sub creation
        log.info("Customer created", extra=dict(stripe_customer_id=customer.id))

    def customer_subscription_created(self, subscription: stripe.Subscription) -> None:
        sub_item_plan_id = subscription.plan.id

        if not sub_item_plan_id:
            log.warning(
                "Subscription created, but missing plan_id",
                extra=dict(
                    stripe_customer_id=subscription.customer,
                    ownerid=subscription.metadata.get("obo_organization"),
                    subscription_plan=subscription.plan,
                ),
            )
            return

        if sub_item_plan_id not in settings.STRIPE_PLAN_VALS:
            log.warning(
                "Subscription creation requested for invalid plan",
                extra=dict(
                    stripe_customer_id=subscription.customer,
                    ownerid=subscription.metadata.get("obo_organization"),
                    plan_id=sub_item_plan_id,
                ),
            )
            return

        plan_name = settings.STRIPE_PLAN_VALS[sub_item_plan_id]

        log.info(
            "Subscription created for customer",
            extra=dict(
                stripe_customer_id=subscription.customer,
                stripe_subscription_id=subscription.id,
                ownerid=subscription.metadata.get("obo_organization"),
                plan=plan_name,
                quantity=subscription.quantity,
            ),
        )
        owner = Owner.objects.get(ownerid=subscription.metadata.get("obo_organization"))
        owner.stripe_subscription_id = subscription.id
        owner.stripe_customer_id = subscription.customer
        owner.save()

        plan_service = PlanService(current_org=owner)
        plan_service.expire_trial_when_upgrading()

        plan_service.update_plan(name=plan_name, user_count=subscription.quantity)

        log.info(
            "Successfully updated customer plan info",
            extra=dict(
                stripe_subscription_id=subscription.id,
                stripe_customer_id=subscription.customer,
                plan=plan_name,
                quantity=subscription.quantity,
            ),
        )

        self._log_updated(1)

    def customer_subscription_updated(self, subscription: stripe.Subscription) -> None:
        owners: QuerySet[Owner] = Owner.objects.filter(
            stripe_subscription_id=subscription.id,
            stripe_customer_id=subscription.customer,
        )
        if not owners.exists():
            log.error(
                "Subscription update requested with invalid plan",
                extra=dict(
                    stripe_subscription_id=subscription.id,
                    stripe_customer_id=subscription.customer,
                    plan_id=subscription.plan.id,
                ),
            )
            return

        indication_of_payment_failure = getattr(subscription, "pending_update", None)
        if indication_of_payment_failure:
            # payment failed, raise this to user by setting as delinquent
            owner.delinquent = True
            owner.save()
            log.info(
                f"Stripe subscription upgrade failed for owner {owner.ownerid}",
                extra=dict(pending_update=indication_of_payment_failure),
            )
            return

        # Properly attach the payment method on the customer
        # This hook will be called after a checkout session completes,
        # updating the subscription created with it
        default_payment_method = subscription.default_payment_method
        if default_payment_method:
            stripe.PaymentMethod.attach(
                default_payment_method, customer=subscription.customer
            )
            stripe.Customer.modify(
                subscription.customer,
                invoice_settings={"default_payment_method": default_payment_method},
            )

        subscription_schedule_id = subscription.schedule
        plan_services = [PlanService(current_org=owner) for owner in owners]

        # Only update if there isn't a scheduled subscription
        if not subscription.schedule:
            plan_service = PlanService(current_org=owner)
            if subscription.status == "incomplete_expired":
                log.info(
                    "Subscription status updated to incomplete_expired, cancelling to free",
                    extra=dict(
                        stripe_subscription_id=subscription.id,
                        stripe_customer_id=subscription.customer,
                    ),
                )
                for service in plan_services:
                    service.set_default_plan_data()
                # TODO: think of how to create services for different objects/classes to delegate responsibilities that are not
                # from the owner
                for owner in owners:
                    owner.repository_set.update(active=False, activated=False)
                return

            sub_item_plan_id = subscription.plan.id
            if sub_item_plan_id not in settings.STRIPE_PLAN_VALS:
                log.error(
                    "Subscription update requested with invalid plan",
                    extra=dict(
                        stripe_subscription_id=subscription.id,
                        stripe_customer_id=subscription.customer,
                        plan_id=sub_item_plan_id,
                    ),
                )
                return

            plan_name = settings.STRIPE_PLAN_VALS[sub_item_plan_id]

            for service in plan_services:
                service.update_plan(name=plan_name, user_count=subscription.quantity)

            log.info(
                "Successfully updated customer subscription",
                extra=dict(
                    stripe_subscription_id=subscription.id,
                    stripe_customer_id=subscription.customer,
                    plan=plan_name,
                    quantity=subscription.quantity,
                ),
            )

    def customer_updated(self, customer: stripe.Customer) -> None:
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

    def checkout_session_completed(
        self, checkout_session: stripe.checkout.Session
    ) -> None:
        log.info(
            "Checkout session completed",
            extra=dict(
                ownerid=checkout_session.client_reference_id,
                stripe_customer_id=checkout_session.customer,
            ),
        )
        owner = Owner.objects.get(ownerid=checkout_session.client_reference_id)
        owner.stripe_customer_id = checkout_session.customer
        owner.save()

        self._log_updated(1)

    def post(self, request: HttpRequest, *args, **kwargs) -> Response:
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
        except stripe.SignatureVerificationError as e:
            log.warning(f"Stripe webhook event received with invalid signature -- {e}")
            return Response("Invalid signature", status=status.HTTP_400_BAD_REQUEST)
        if self.event.type not in StripeWebhookEvents.subscribed_events:
            log.warning(
                "Unsupported Stripe webhook event received, exiting",
                extra=dict(stripe_webhook_event=self.event.type),
            )
            return Response("Unsupported event type", status=204)

        log.info(
            "Stripe webhook event received",
            extra=dict(stripe_webhook_event=self.event.type),
        )

        # Converts event names of the format X.Y.Z into X_Y_Z, and calls
        # the relevant method in this class
        getattr(self, self.event.type.replace(".", "_"))(self.event.data.object)

        return Response(status=status.HTTP_204_NO_CONTENT)
