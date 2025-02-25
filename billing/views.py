import logging
from datetime import datetime
from typing import Any, List

import stripe
from django.conf import settings
from django.db.models import QuerySet
from django.http import HttpRequest
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from shared.plan.service import PlanService

from billing.helpers import get_all_admins_for_owners
from codecov_auth.models import Owner, Plan
from services.task.task import TaskService

from .constants import StripeHTTPHeaders, StripeWebhookEvents

if settings.STRIPE_API_KEY:
    stripe.api_key = settings.STRIPE_API_KEY
    stripe.api_version = "2024-12-18.acacia"

log = logging.getLogger(__name__)


class StripeWebhookHandler(APIView):
    permission_classes = [AllowAny]

    def _log_updated(self, updated: List[Owner]) -> None:
        if len(updated) >= 1:
            log.info(
                f"Successfully updated info for {len(updated)} owner(s)",
                extra=dict(owners=[owner.ownerid for owner in updated]),
            )

    def invoice_payment_succeeded(self, invoice: stripe.Invoice) -> None:
        log.info(
            "Invoice Payment Succeeded - Setting delinquency status False",
            extra=dict(
                stripe_customer_id=invoice.customer,
                stripe_subscription_id=invoice.subscription,
            ),
        )
        owners: QuerySet[Owner] = Owner.objects.filter(
            stripe_customer_id=invoice.customer,
            stripe_subscription_id=invoice.subscription,
            delinquent=True,
        )

        if not owners.exists():
            return

        admins = get_all_admins_for_owners(owners)
        owners.update(delinquent=False)
        self._log_updated(list(owners))

        # Send a success email to all admins

        task_service = TaskService()
        template_vars = {
            "amount": invoice.total / 100,
            "date": datetime.now().strftime("%B %-d, %Y"),
            "cta_link": invoice.hosted_invoice_url,
        }

        for admin in admins:
            if admin.email:
                task_service.send_email(
                    to_addr=admin.email,
                    subject="You're all set",
                    template_name="success-after-failed-payment",
                    **template_vars,
                )

        # temporary just making sure these look okay in the real world
        task_service.send_email(
            to_addr="spencer.murray@sentry.io",
            subject="You're all set",
            template_name="success-after-failed-payment",
            **template_vars,
        )

    def invoice_payment_failed(self, invoice: stripe.Invoice) -> None:
        """
        Stripe invoice.payment_failed webhook event is emitted when an invoice payment fails
        (initial or recurring). Note that delayed payment methods (including ACH with
        microdeposits) may have a failed initial invoice until the account is verified.
        """
        if invoice.default_payment_method is None:
            if invoice.payment_intent:
                payment_intent = stripe.PaymentIntent.retrieve(invoice.payment_intent)
                if (
                    payment_intent
                    and payment_intent.get("status") == "requires_action"
                    and payment_intent.get("next_action", {}).get("type")
                    == "verify_with_microdeposits"
                ):
                    log.info(
                        "Invoice payment failed but still awaiting known customer action, skipping Delinquency actions",
                        extra=dict(
                            stripe_customer_id=invoice.customer,
                            stripe_subscription_id=invoice.subscription,
                            payment_intent_id=invoice.payment_intent,
                            payment_intent_status=payment_intent.status,
                        ),
                    )
                    return

        log.info(
            "Invoice Payment Failed - Setting Delinquency status True",
            extra=dict(
                stripe_customer_id=invoice.customer,
                stripe_subscription_id=invoice.subscription,
            ),
        )
        owners: QuerySet[Owner] = Owner.objects.filter(
            stripe_customer_id=invoice.customer,
            stripe_subscription_id=invoice.subscription,
        )
        owners.update(delinquent=True)
        self._log_updated(list(owners))

        # Send failed payment email to all owner admins
        admins = get_all_admins_for_owners(owners)

        task_service = TaskService()
        payment_intent = stripe.PaymentIntent.retrieve(
            invoice["payment_intent"], expand=["payment_method"]
        )

        try:
            card = payment_intent.payment_method.card
        except AttributeError:
            card = None

        template_vars = {
            "amount": invoice.total / 100,
            "card_type": card.brand if card else None,
            "last_four": card.last4 if card else None,
            "cta_link": invoice.hosted_invoice_url,
            "date": datetime.now().strftime("%B %-d, %Y"),
        }

        for admin in admins:
            if admin.email:
                task_service.send_email(
                    to_addr=admin.email,
                    subject="Your Codecov payment failed",
                    template_name="failed-payment",
                    name=admin.username,
                    **template_vars,
                )

        # temporary just making sure these look okay in the real world
        task_service.send_email(
            to_addr="spencer.murray@sentry.io",
            subject="Your Codecov payment failed",
            template_name="failed-payment",
            name="spalmurray-codecov",
            **template_vars,
        )

    def customer_subscription_deleted(self, subscription: stripe.Subscription) -> None:
        """
        Stripe customer.subscription.deleted webhook event is emitted when a subscription is deleted.
        This happens when an org goes from paid to free (see payment_service.delete_subscription)
        or when cleaning up an incomplete subscription that never activated (e.g., abandoned async
        ACH microdeposits verification).
        """
        log.info(
            "Customer Subscription Deleted - Setting free plan and deactivating repos for stripe customer",
            extra=dict(
                stripe_subscription_id=subscription.id,
                stripe_customer_id=subscription.customer,
                previous_subscription_status=subscription.status,
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
            plan_service = PlanService(current_org=owner)
            plan_service.set_default_plan_data()
            owner.repository_set.update(active=False, activated=False)

        self._log_updated(list(owners))

    def subscription_schedule_created(
        self, schedule: stripe.SubscriptionSchedule
    ) -> None:
        subscription = stripe.Subscription.retrieve(schedule["subscription"])
        sub_item_plan_id = subscription.plan.id
        plan_name = Plan.objects.get(stripe_id=sub_item_plan_id).name
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
            plan_name = Plan.objects.get(stripe_id=plan_id).name
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

        sub_item_plan_id = subscription.plan.id
        plan_name = Plan.objects.get(stripe_id=sub_item_plan_id).name
        for owner in owners:
            plan_service = PlanService(current_org=owner)
            plan_service.update_plan(name=plan_name, user_count=subscription.quantity)

        requesting_user_id = subscription.metadata.get("obo")
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
        """
        Stripe customer.subscription.created webhook event is emitted when a subscription is created.
        This happens when an owner completes a CheckoutSession for a new subscription.
        """
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

        try:
            plan = Plan.objects.get(stripe_id=sub_item_plan_id)
        except Plan.DoesNotExist:
            log.warning(
                "Subscription creation requested for invalid plan",
                extra=dict(
                    stripe_customer_id=subscription.customer,
                    ownerid=subscription.metadata.get("obo_organization"),
                    plan_id=sub_item_plan_id,
                ),
            )
            return

        plan_name = plan.name

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
        # add the subscription_id and customer_id to the owner
        owner = Owner.objects.get(ownerid=subscription.metadata.get("obo_organization"))
        owner.stripe_subscription_id = subscription.id
        owner.stripe_customer_id = subscription.customer
        owner.save()

        # We may reach here if the subscription was created with a payment method
        # that is awaiting verification (e.g. ACH microdeposits)
        if self._has_unverified_initial_payment_method(subscription):
            log.info(
                "Subscription has pending initial payment verification - will upgrade plan after initial invoice payment",
                extra=dict(
                    subscription_id=subscription.id,
                    customer_id=subscription.customer,
                ),
            )
            return

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

        self._log_updated([owner])

    def _has_unverified_initial_payment_method(
        self, subscription: stripe.Subscription
    ) -> bool:
        """
        Helper method to check if a subscription's latest invoice has a payment intent
        that requires verification (e.g. ACH microdeposits). This indicates that
        there is an unverified payment method from the initial CheckoutSession.
        """
        latest_invoice = stripe.Invoice.retrieve(subscription.latest_invoice)
        if latest_invoice and latest_invoice.payment_intent:
            payment_intent = stripe.PaymentIntent.retrieve(
                latest_invoice.payment_intent
            )
            return (
                payment_intent
                and payment_intent.get("status") == "requires_action"
                and payment_intent.get("next_action")
                and payment_intent.get("next_action", {}).get("type")
                == "verify_with_microdeposits"
            )
        return False

    def customer_subscription_updated(self, subscription: stripe.Subscription) -> None:
        """
        Stripe customer.subscription.updated webhook event is emitted when a subscription is updated.
        This can happen when an owner updates the subscription's default payment method using our
        update_payment_method api
        """
        owners: QuerySet[Owner] = Owner.objects.filter(
            stripe_subscription_id=subscription.id,
            stripe_customer_id=subscription.customer,
        )
        if not owners.exists():
            log.error(
                "Subscription update requested with for plan attached to no owners",
                extra=dict(
                    stripe_subscription_id=subscription.id,
                    stripe_customer_id=subscription.customer,
                    plan_id=subscription.plan.id,
                ),
            )
            return

        if self._has_unverified_initial_payment_method(subscription):
            log.info(
                "Subscription has pending initial payment verification - will upgrade plan after initial invoice payment",
                extra=dict(
                    subscription_id=subscription.id,
                    customer_id=subscription.customer,
                ),
            )
            return

        indication_of_payment_failure = getattr(subscription, "pending_update", None)
        if indication_of_payment_failure:
            # payment failed, raise this to user by setting as delinquent
            owners.update(delinquent=True)
            log.info(
                "Stripe subscription upgrade failed",
                extra=dict(
                    pending_update=indication_of_payment_failure,
                    stripe_subscription_id=subscription.id,
                    stripe_customer_id=subscription.customer,
                    owners=[owner.ownerid for owner in owners],
                ),
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

        try:
            plan = Plan.objects.get(stripe_id=subscription.plan.id)
        except Plan.DoesNotExist:
            log.error(
                "Subscription update requested with invalid plan",
                extra=dict(
                    stripe_subscription_id=subscription.id,
                    stripe_customer_id=subscription.customer,
                    plan_id=subscription.plan.id,
                ),
            )
            return

        subscription_schedule_id = subscription.schedule
        plan_name = plan.name
        incomplete_expired = subscription.status == "incomplete_expired"

        # Only update if there is not a scheduled subscription
        if subscription_schedule_id:
            return

        owner_ids = []
        for owner in owners:
            plan_service = PlanService(current_org=owner)
            if incomplete_expired:
                plan_service.set_default_plan_data()
                owner.repository_set.update(active=False, activated=False)
            else:
                plan_service.update_plan(
                    name=plan_name, user_count=subscription.quantity
                )
            owner_ids.append(owner.ownerid)

        if incomplete_expired:
            log.info(
                "Subscription status updated to incomplete_expired, cancelling to free",
                extra=dict(
                    stripe_subscription_id=subscription.id,
                    stripe_customer_id=subscription.customer,
                    owners=owner_ids,
                ),
            )
            return
        log.info(
            "Successfully updated customer subscription",
            extra=dict(
                stripe_subscription_id=subscription.id,
                stripe_customer_id=subscription.customer,
                plan=plan_name,
                quantity=subscription.quantity,
                owners=owner_ids,
            ),
        )

    def customer_updated(self, customer: stripe.Customer) -> None:
        new_default_payment_method = customer["invoice_settings"][
            "default_payment_method"
        ]

        if new_default_payment_method is None:
            return

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
        owner.stripe_subscription_id = checkout_session.subscription
        owner.save()

        self._log_updated([owner])

    def _check_and_handle_delayed_notification_payment_methods(
        self, customer_id: str, payment_method_id: str
    ):
        """
        Helper method to handle payment methods that require delayed verification (like ACH).
        When verification succeeds, this attaches the payment method to the customer and sets
        it as the default payment method for both the customer and subscription.
        """
        payment_method = stripe.PaymentMethod.retrieve(payment_method_id)

        is_us_bank_account = payment_method.type == "us_bank_account" and hasattr(
            payment_method, "us_bank_account"
        )

        should_set_as_default = is_us_bank_account

        # attach the payment method + set as default on the invoice and subscription
        if should_set_as_default:
            # retrieve the number of owners to update
            owners = Owner.objects.filter(
                stripe_customer_id=customer_id, stripe_subscription_id__isnull=False
            )

            if owners.exists():
                # Even if multiple results are returned, these two stripe calls are
                # just for a single customer
                stripe.PaymentMethod.attach(payment_method, customer=customer_id)
                stripe.Customer.modify(
                    customer_id,
                    invoice_settings={"default_payment_method": payment_method},
                )

                # But this one is for each subscription an owner may have
                for owner in owners:
                    stripe.Subscription.modify(
                        owner.stripe_subscription_id,
                        default_payment_method=payment_method,
                    )
            else:
                log.error(
                    "No owners found with that customer_id, something went wrong",
                    extra=dict(customer_id=customer_id),
                )

    def payment_intent_succeeded(self, payment_intent: stripe.PaymentIntent) -> None:
        """
        Stripe payment_intent.succeeded webhook event is emitted when a
        payment intent goes to a success state.
        We create a Stripe PaymentIntent for the initial checkout session.
        """
        log.info(
            "Payment intent succeeded",
            extra=dict(
                stripe_customer_id=payment_intent.customer,
                payment_intent_id=payment_intent.id,
                payment_method_type=payment_intent.payment_method,
            ),
        )

        self._check_and_handle_delayed_notification_payment_methods(
            payment_intent.customer, payment_intent.payment_method
        )

    def setup_intent_succeeded(self, setup_intent: stripe.SetupIntent) -> None:
        """
        Stripe setup_intent.succeeded webhook event is emitted when a setup intent
        goes to a success state. We create a Stripe SetupIntent for the gazebo UI
        PaymentElement to modify payment methods.
        """
        log.info(
            "Setup intent succeeded",
            extra=dict(
                stripe_customer_id=setup_intent.customer,
                setup_intent_id=setup_intent.id,
                payment_method_type=setup_intent.payment_method,
            ),
        )

        self._check_and_handle_delayed_notification_payment_methods(
            setup_intent.customer, setup_intent.payment_method
        )

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
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
