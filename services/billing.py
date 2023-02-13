import logging
from abc import ABC, abstractmethod

import stripe
from django.conf import settings

from billing.constants import (
    ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS,
    FREE_PLAN_REPRESENTATIONS,
    PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS,
    REMOVED_INVOICE_STATUSES,
    USER_PLAN_REPRESENTATIONS,
)
from codecov_auth.models import Owner
from services.segment import SegmentService

log = logging.getLogger(__name__)

SCHEDULE_RELEASE_OFFSET = 10

if settings.STRIPE_API_KEY:
    stripe.api_key = settings.STRIPE_API_KEY


def _log_stripe_error(method):
    def catch_and_raise(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except stripe.error.StripeError as e:
            log.warning(e.user_message)
            raise

    return catch_and_raise


class AbstractPaymentService(ABC):
    @abstractmethod
    def get_invoice(self, owner, invoice_id):
        pass

    @abstractmethod
    def list_filtered_invoices(self, owner, limit=10):
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

    @abstractmethod
    def get_subscription(self, owner):
        pass

    @abstractmethod
    def update_payment_method(self, owner, payment_method):
        pass

    @abstractmethod
    def get_schedule(self, owner):
        pass

    @abstractmethod
    def apply_cancellation_discount(self, owner: Owner):
        pass


class StripeService(AbstractPaymentService):
    def __init__(self, requesting_user):
        if settings.STRIPE_API_KEY is None:
            log.critical(
                "Missing stripe API key configuration -- communication with stripe won't be possible."
            )
        if not isinstance(requesting_user, Owner):
            raise Exception(
                "StripeService requires requesting_user to be Owner instance"
            )

        self.requesting_user = requesting_user

    def _get_checkout_session_and_subscription_metadata(self, owner):
        return {
            "service": owner.service,
            "obo_organization": owner.ownerid,
            "username": owner.username,
            "obo_name": self.requesting_user.name,
            "obo_email": self.requesting_user.email,
            "obo": self.requesting_user.ownerid,
        }

    @_log_stripe_error
    def get_invoice(self, owner, invoice_id):
        log.info(
            f"Fetching invoice {invoice_id} from Stripe for ownerid {owner.ownerid}"
        )
        try:
            invoice = stripe.Invoice.retrieve(invoice_id)
        except stripe.error.InvalidRequestError as e:
            log.info(f"invoice {invoice_id} not found for owner {owner.ownerid}")
            return None
        if invoice["customer"] != owner.stripe_customer_id:
            log.info(
                f"customer id ({invoice['customer']}) on invoice does not match the owner customer id ({owner.stripe_customer_id})"
            )
            return None
        return invoice

    def filter_invoices_by_status(self, invoice):
        if invoice["status"] and invoice["status"] not in REMOVED_INVOICE_STATUSES:
            return invoice

    def filter_invoices_by_total(self, invoice):
        if invoice["total"] and invoice["total"] != 0:
            return invoice

    @_log_stripe_error
    def list_filtered_invoices(self, owner, limit=10):
        log.info(f"Fetching invoices from Stripe for ownerid {owner.ownerid}")
        if owner.stripe_customer_id is None:
            log.info("stripe_customer_id is None, not fetching invoices")
            return []
        invoices = stripe.Invoice.list(customer=owner.stripe_customer_id, limit=limit)[
            "data"
        ]
        invoices_filtered_by_status = filter(self.filter_invoices_by_status, invoices)
        invoices_filtered_by_status_and_total = filter(
            self.filter_invoices_by_total, invoices_filtered_by_status
        )
        return list(invoices_filtered_by_status_and_total)

    @_log_stripe_error
    def delete_subscription(self, owner):
        subscription = stripe.Subscription.retrieve(owner.stripe_subscription_id)
        subscription_schedule_id = subscription.schedule

        if owner.plan not in USER_PLAN_REPRESENTATIONS:
            log.info(
                f"Downgrade to basic plan from legacy plan for owner {owner.ownerid} by user #{self.requesting_user.ownerid}",
                extra=dict(ownerid=owner.ownerid),
            )
            if not subscription_schedule_id:
                log.info(
                    f"Deleting stripe subscription for owner {owner.ownerid} by user #{self.requesting_user.ownerid}",
                    extra=dict(ownerid=owner.ownerid),
                )
                stripe.Subscription.delete(owner.stripe_subscription_id, prorate=False)
            else:
                log.info(
                    f"Cancelling schedule and deleting subscription for owner {owner.ownerid} by user #{self.requesting_user.ownerid}",
                    extra=dict(ownerid=owner.ownerid),
                )
                stripe.SubscriptionSchedule.cancel(subscription_schedule_id)
            owner.set_basic_plan()
        else:
            log.info(
                f"Downgrade to basic plan from user plan for owner {owner.ownerid} by user #{self.requesting_user.ownerid}",
                extra=dict(ownerid=owner.ownerid),
            )
            if subscription_schedule_id:
                log.info(
                    f"Releasing subscription from schedule for owner {owner.ownerid} by user #{self.requesting_user.ownerid}",
                    extra=dict(ownerid=owner.ownerid),
                )
                stripe.SubscriptionSchedule.release(subscription_schedule_id)

            stripe.Subscription.modify(
                owner.stripe_subscription_id, cancel_at_period_end=True, prorate=False
            )

    @_log_stripe_error
    def get_subscription(self, owner):
        if not owner.stripe_subscription_id:
            return None
        return stripe.Subscription.retrieve(
            owner.stripe_subscription_id,
            expand=[
                "latest_invoice",
                "customer",
                "customer.invoice_settings.default_payment_method",
            ],
        )

    @_log_stripe_error
    def get_schedule(self, owner):
        if not owner.stripe_subscription_id:
            return None

        subscription = self.get_subscription(owner)
        subscription_schedule_id = subscription.schedule

        if not subscription_schedule_id:
            return None

        return stripe.SubscriptionSchedule.retrieve(subscription_schedule_id)

    @_log_stripe_error
    def modify_subscription(self, owner, desired_plan):
        subscription = stripe.Subscription.retrieve(owner.stripe_subscription_id)
        proration_behavior = self._get_proration_params(owner, desired_plan)
        subscription_schedule_id = subscription.schedule

        # proration_behavior indicates whether we immediately invoice a user or not. We only immediately
        # invoice a user if the user increases the number of seats or if the plan changes from monthly to yearly.
        # An increase in seats and/or plan implies the user is upgrading, hence 'is_upgrading' is a consequence
        # of proration_behavior providing an invoice, in this case, != "none"
        is_upgrading = True if proration_behavior != "none" else False

        # Divide logic bw immediate updates and scheduled updates
        # Immediate updates: when user upgrades seats or plan
        #   If the user is not in a schedule, update immediately
        #   If the user is in a schedule, update the existing schedule
        # Scheduled updates: when the user decreases seats or plan
        #   If the user is not in a schedule, create a schedule
        #   If the user is in a schedule, update the existing schedule

        if is_upgrading:
            if subscription_schedule_id:
                self._modify_subscription_schedule(
                    owner, subscription, subscription_schedule_id, desired_plan
                )
            else:
                log.info(
                    f"Updating Stripe subscription for owner {owner.ownerid} to {desired_plan['value']} by user #{self.requesting_user.ownerid}"
                )
                stripe.Subscription.modify(
                    owner.stripe_subscription_id,
                    cancel_at_period_end=False,
                    items=[
                        {
                            "id": subscription["items"]["data"][0]["id"],
                            "plan": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                            "quantity": desired_plan["quantity"],
                        }
                    ],
                    metadata=self._get_checkout_session_and_subscription_metadata(
                        owner
                    ),
                    proration_behavior=proration_behavior,
                )

                self._segment_modify_subscription(owner, desired_plan)

                owner.plan = desired_plan["value"]
                owner.plan_user_count = desired_plan["quantity"]
                owner.save()

                log.info(
                    f"Stripe subscription modified successfully for owner {owner.ownerid} by user #{self.requesting_user.ownerid}"
                )
        else:
            if subscription_schedule_id:
                self._modify_subscription_schedule(
                    owner, subscription, subscription_schedule_id, desired_plan
                )
            else:
                schedule = stripe.SubscriptionSchedule.create(
                    from_subscription=owner.stripe_subscription_id
                )
                subscription_schedule_id = schedule.id

                self._modify_subscription_schedule(
                    owner, subscription, subscription_schedule_id, desired_plan
                )

    def _segment_modify_subscription(self, owner, desired_plan):
        if owner.plan != desired_plan["value"]:
            SegmentService().account_changed_plan(
                current_user_ownerid=self.requesting_user.ownerid,
                org_ownerid=owner.ownerid,
                plan_details={
                    "new_plan": desired_plan["value"],
                    "previous_plan": owner.plan,
                },
            )

        if owner.plan_user_count and owner.plan_user_count < desired_plan["quantity"]:
            SegmentService().account_increased_users(
                current_user_ownerid=self.requesting_user.ownerid,
                org_ownerid=owner.ownerid,
                plan_details={
                    "new_quantity": desired_plan["quantity"],
                    "old_quantity": owner.plan_user_count,
                    "plan": desired_plan["value"],
                },
            )

    def _modify_subscription_schedule(
        self, owner, subscription, subscription_schedule_id, desired_plan
    ):
        current_subscription_start_date = subscription["current_period_start"]
        current_subscription_end_date = subscription["current_period_end"]

        subscription_item = subscription["items"]["data"][0]
        current_plan = subscription_item["plan"]["name"]
        current_quantity = subscription_item["quantity"]

        stripe.SubscriptionSchedule.modify(
            subscription_schedule_id,
            end_behavior="release",
            phases=[
                {
                    "start_date": current_subscription_start_date,
                    "end_date": current_subscription_end_date,
                    "plans": [
                        {
                            "plan": settings.STRIPE_PLAN_IDS[current_plan],
                            "price": settings.STRIPE_PLAN_IDS[current_plan],
                            "quantity": current_quantity,
                        }
                    ],
                    "proration_behavior": "none",
                },
                {
                    "start_date": current_subscription_end_date,
                    "end_date": current_subscription_end_date + SCHEDULE_RELEASE_OFFSET,
                    "plans": [
                        {
                            "plan": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                            "price": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                            "quantity": desired_plan["quantity"],
                        }
                    ],
                    "proration_behavior": "none",
                },
            ],
            metadata=self._get_checkout_session_and_subscription_metadata(owner),
        )

    def _get_proration_params(self, owner, desired_plan):
        proration_behavior = "none"
        if owner.plan == desired_plan["value"]:
            # Same product, increased number of seats
            if (
                owner.plan_user_count
                and owner.plan_user_count < desired_plan["quantity"]
            ):
                return "always_invoice"
            # Same product, decreased nummber of seats
            return proration_behavior

        elif "m" in owner.plan and "y" in desired_plan["value"]:
            # From monthly to yearly
            return "always_invoice"
        return proration_behavior

    def _get_success_and_cancel_url(self, owner):
        short_services = {"github": "gh", "bitbucket": "bb", "gitlab": "gl"}
        base_path = f"/plan/{short_services[owner.service]}/{owner.username}"
        success_url = f"{settings.CODECOV_DASHBOARD_URL}{base_path}?success"
        cancel_url = f"{settings.CODECOV_DASHBOARD_URL}{base_path}?cancel"
        return success_url, cancel_url

    @_log_stripe_error
    def create_checkout_session(self, owner, desired_plan):
        success_url, cancel_url = self._get_success_and_cancel_url(owner)
        log.info("Creating Stripe Checkout Session for owner: {owner.ownerid}")
        session = stripe.checkout.Session.create(
            billing_address_collection="required",
            payment_method_types=["card"],
            client_reference_id=owner.ownerid,
            customer=owner.stripe_customer_id,
            customer_email=owner.email,
            success_url=success_url,
            cancel_url=cancel_url,
            subscription_data={
                "items": [
                    {
                        "plan": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                        "quantity": desired_plan["quantity"],
                    }
                ],
                "payment_behavior": "allow_incomplete",
                "metadata": self._get_checkout_session_and_subscription_metadata(owner),
            },
        )
        log.info(
            f"Stripe Checkout Session created successfully for owner {owner.ownerid} by user #{self.requesting_user.ownerid}"
        )
        return session["id"]

    @_log_stripe_error
    def update_payment_method(self, owner, payment_method):
        log.info(f"Stripe update payment method for owner {owner.ownerid}")
        if owner.stripe_subscription_id is None:
            log.info(
                f"stripe_subscription_id is None, no updating card for owner {owner.ownerid}"
            )
            return None
        # attach the payment method + set ass default on the invoice and subscription
        stripe.PaymentMethod.attach(payment_method, customer=owner.stripe_customer_id)
        stripe.Customer.modify(
            owner.stripe_customer_id,
            invoice_settings={"default_payment_method": payment_method},
        )
        log.info(
            f"Stripe success update payment method for owner {owner.ownerid} by user #{self.requesting_user.ownerid}"
        )

    @_log_stripe_error
    def apply_cancellation_discount(self, owner: Owner):
        if owner.stripe_subscription_id is None:
            log.info(
                f"stripe_subscription_id is None, not applying cancellation coupon for owner {owner.ownerid}"
            )
            return

        if not owner.stripe_coupon_id:
            log.info(f"Creating Stripe cancellation coupon for owner {owner.ownerid}")
            coupon = stripe.Coupon.create(
                percent_off=30.0,
                duration="repeating",
                duration_in_months=6,
                name="30% off for 6 months",
                max_redemptions=1,
                metadata={
                    "ownerid": owner.ownerid,
                    "username": owner.username,
                },
            )

            owner.stripe_coupon_id = coupon.id
            owner.save()

        log.info(
            f"Applying cancellation coupon to Stripe subscription for owner {owner.ownerid}"
        )
        stripe.Subscription.modify(
            owner.stripe_subscription_id,
            coupon=owner.stripe_coupon_id,
        )


class EnterprisePaymentService(AbstractPaymentService):
    # enterprise has no payments setup so these are all noops

    def get_invoice(self, owner, invoice_id):
        pass

    def list_filtered_invoices(self, owner, limit=10):
        pass

    def delete_subscription(self, owner):
        pass

    def modify_subscription(self, owner, plan):
        pass

    def create_checkout_session(self, owner, plan):
        pass

    def get_subscription(self, owner):
        pass

    def update_payment_method(self, owner, payment_method):
        pass

    def get_schedule(self, owner):
        pass

    def apply_cancellation_discount(self, owner: Owner):
        pass


class BillingService:
    payment_service = None

    def __init__(self, payment_service=None, requesting_user=None):
        if payment_service is None:
            if settings.IS_ENTERPRISE:
                self.payment_service = EnterprisePaymentService()
            else:
                self.payment_service = StripeService(requesting_user=requesting_user)
        else:
            self.payment_service = payment_service

        if not issubclass(type(self.payment_service), AbstractPaymentService):
            raise Exception(
                "self.payment_service must subclass AbstractPaymentService!"
            )

    def get_subscription(self, owner):
        return self.payment_service.get_subscription(owner)

    def get_schedule(self, owner):
        return self.payment_service.get_schedule(owner)

    def get_invoice(self, owner, invoice_id):
        return self.payment_service.get_invoice(owner, invoice_id)

    def list_filtered_invoices(self, owner, limit=10):
        return self.payment_service.list_filtered_invoices(owner, limit)

    def update_plan(self, owner, desired_plan):
        """
        Takes an owner and desired plan, and updates the owner's plan. Depending
        on current state, might create a stripe checkout session and return
        the checkout session's ID, which is a string. Otherwise returns None.
        """
        if desired_plan["value"] in FREE_PLAN_REPRESENTATIONS:
            if owner.stripe_subscription_id is not None:
                self.payment_service.delete_subscription(owner)
            else:
                owner.set_basic_plan()
        elif (
            desired_plan["value"] in PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS
            or desired_plan["value"] in ENTERPRISE_CLOUD_USER_PLAN_REPRESENTATIONS
        ):
            if owner.stripe_subscription_id is not None:
                self.payment_service.modify_subscription(owner, desired_plan)
            else:
                return self.payment_service.create_checkout_session(owner, desired_plan)
        else:
            log.warning(
                f"Attempted to transition to non-existent or legacy plan: "
                f"owner {owner.ownerid}, plan: {desired_plan}"
            )

    def update_payment_method(self, owner, payment_method):
        """
        Takes an owner and a new card. card is an object coming directly from
        the front-end; without any validation, as payment service can handle
        the card data differently
        """
        return self.payment_service.update_payment_method(owner, payment_method)

    def apply_cancellation_discount(self, owner: Owner):
        return self.payment_service.apply_cancellation_discount(owner)
