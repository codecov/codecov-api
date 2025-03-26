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

    def invoice_payment_failed(self, invoice: stripe.Invoice) -> None:
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

    def customer_subscription_deleted(self, subscription: stripe.Subscription) -> None:
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
        owner = Owner.objects.get(ownerid=subscription.metadata.get("obo_organization"))
        owner.stripe_subscription_id = subscription.id
        owner.stripe_customer_id = subscription.customer
        owner.save()

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
        payment_method = stripe.PaymentMethod.retrieve(payment_method_id)

        is_us_bank_account = payment_method.type == "us_bank_account" and hasattr(
            payment_method, "us_bank_account"
        )

        should_set_as_default = is_us_bank_account

        if should_set_as_default:
            owners = Owner.objects.filter(
                stripe_customer_id=customer_id, stripe_subscription_id__isnull=False
            )

            if owners.exists():
                stripe.PaymentMethod.attach(payment_method, customer=customer_id)
                stripe.Customer.modify(
                    customer_id,
                    invoice_settings={"default_payment_method": payment_method},
                )

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

    # --- Additional Functions for Robust Flows ---
