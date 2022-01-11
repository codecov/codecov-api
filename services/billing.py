import logging
from abc import ABC, abstractmethod

import stripe
from django.conf import settings
from stripe.api_resources import subscription_schedule

from billing.constants import (
    PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS,
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

    @abstractmethod
    def get_subscription(self, owner):
        pass

    @abstractmethod
    def update_payment_method(self, owner, payment_method):
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
        print("Testing - Get invoice")
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

    @_log_stripe_error
    def list_invoices(self, owner, limit=10):
        print("Testing - List invoices")
        log.info(f"Fetching invoices from Stripe for ownerid {owner.ownerid}")
        if owner.stripe_customer_id is None:
            log.info("stripe_customer_id is None, not fetching invoices")
            return []
        return stripe.Invoice.list(customer=owner.stripe_customer_id, limit=limit)[
            "data"
        ]

    @_log_stripe_error
    def delete_subscription(self, owner):
        # TODO: add a check to see if there is a schedule, if so, cancel the schedule instead
        print("Testing - Delete subscription")
        if owner.plan not in USER_PLAN_REPRESENTATIONS:
            log.info(
                f"Downgrade to free plan from legacy plan for owner {owner.ownerid} by user #{self.requesting_user.ownerid}"
            )
            stripe.Subscription.delete(owner.stripe_subscription_id, prorate=False)
            owner.set_free_plan()
        else:
            log.info(
                f"Downgrade to free plan from user plan for owner {owner.ownerid} by user #{self.requesting_user.ownerid}"
            )
            stripe.Subscription.modify(
                owner.stripe_subscription_id, cancel_at_period_end=True, prorate=False
            )

    @_log_stripe_error
    def get_subscription(self, owner):
        print("Testing - Get subscription")
        if owner.stripe_subscription_id is None:
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
    def modify_subscription(self, owner, desired_plan):
        # Enters when I modify bw paid plans or change user numbers within a paid plan
        print("Testing - Modify subscription")
        # This should be only in the upgrading part
        log.info(
            f"Updating Stripe subscription for owner {owner.ownerid} to {desired_plan['value']} by user #{self.requesting_user.ownerid}"
        )
        subscription = stripe.Subscription.retrieve(owner.stripe_subscription_id)
        proration_behavior = self._get_proration_params(owner, desired_plan)
        subscription_schedule_id = subscription.schedule
        is_upgrading = True if proration_behavior != "none" else False
        subscription_id = owner.stripe_subscription_id
        # stripe.SubscriptionSchedule.release(
        #     subscription.schedule,
        # )

        # return

        # $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
        # Divide logic bw immediate updates and scheduled updates
        # Immediate updates: when user upgrades seats or plan
        #   If the user is not in a schedule, update immediately
        #   If the user is in a schedule, update the existing schedule
        # Scheduled updates: when the user decreases seats or plan
        #   If the user is not in a schedule, create a schedule
        #   If the user is in a schedule, update the existing schedule
        # $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

        if is_upgrading:
            # If the user is in a schedule, update the existing schedule
            if subscription_schedule_id is not None:
                print("Testing - updating schedule in upgrade")
                self._modify_subscription_schedule(owner, subscription, subscription_schedule_id, desired_plan)
            # Else since the user is not in a schedule, update immediately
            else:
                print("Testing - upgrading immediately")
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
                    metadata=self._get_checkout_session_and_subscription_metadata(owner),
                    proration_behavior=proration_behavior,
                )
                # Segment analytics
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

                owner.plan = desired_plan["value"]
                owner.plan_user_count = desired_plan["quantity"]
                owner.save()

                log.info(
                    f"Stripe subscription modified successfully for owner {owner.ownerid} by user #{self.requesting_user.ownerid}"
                )
        else:
            # If the user is in a schedule, update the existing schedule
            if subscription_schedule_id is not None:
                print("Testing - updating schedule in downgrade")
                self._modify_subscription_schedule(owner, subscription, subscription_schedule_id, desired_plan)
            # Else since the user is not in a schedule, create a schedule
            else:
                print("Testing - creating a schedule")
                schedule = stripe.SubscriptionSchedule.create(
                    from_subscription=subscription_id,
                )
                subscription_schedule_id = schedule.id

                self._modify_subscription_schedule(owner, subscription, subscription_schedule_id, desired_plan)
                # Potentially have to add another schedule.modify call to adjust for the proration_behavior (although that doesn't seem to be taking a lot of effect)

    def _modify_subscription_schedule(self, owner, subscription, subscription_schedule_id, desired_plan):
        print("updating existing schedule to update schedule with existing info")
        current_subscription_start_date = subscription["current_period_start"]
        current_subscription_end_date = subscription["current_period_end"]

        subscription_item = subscription["items"]["data"][0]
        current_plan = subscription_item["plan"]["name"]
        current_quantity = subscription_item["quantity"]

        print("subscription")
        print(subscription)

        stripe.SubscriptionSchedule.modify(
            subscription_schedule_id,
            end_behavior="release",
            phases = [{
                "start_date": current_subscription_start_date,
                "end_date": current_subscription_end_date,
                "plans": [{
                    "plan": settings.STRIPE_PLAN_IDS[current_plan],
                    "price": settings.STRIPE_PLAN_IDS[current_plan],
                    "quantity": current_quantity
                }],
            }, {
                "start_date": current_subscription_end_date,
                "end_date": current_subscription_end_date+SCHEDULE_RELEASE_OFFSET,
                "plans": [{
                    "plan": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                    "price": settings.STRIPE_PLAN_IDS[desired_plan["value"]],
                    "quantity": desired_plan["quantity"],
                }]
            }],
            metadata=self._get_checkout_session_and_subscription_metadata(owner),
            proration_behavior="none",
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
        short_services = {
            "github": "gh",
            "bitbucket": "bb",
            "gitlab": "gl",
        }
        base_path = f"/account/{short_services[owner.service]}/{owner.username}/billing"
        success_url = f"{settings.CODECOV_DASHBOARD_URL}{base_path}?success"
        cancel_url = f"{settings.CODECOV_DASHBOARD_URL}{base_path}?cancel"
        return success_url, cancel_url

    @_log_stripe_error
    def create_checkout_session(self, owner, desired_plan):
        print("Testing - Create checkout session")
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
        print("Testing - Update payment method")
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


class BillingService:
    payment_service = None

    def __init__(self, payment_service=None, requesting_user=None):
        if payment_service is None:
            self.payment_service = StripeService(requesting_user=requesting_user)
        else:
            self.payment_service = payment_service

        if not issubclass(type(self.payment_service), AbstractPaymentService):
            raise Exception(
                "self.payment_service must subclass AbstractPaymentService!"
            )

    def get_subscription(self, owner):
        return self.payment_service.get_subscription(owner)

    def get_invoice(self, owner, invoice_id):
        return self.payment_service.get_invoice(owner, invoice_id)

    def list_invoices(self, owner, limit=10):
        return self.payment_service.list_invoices(owner, limit)

    def update_plan(self, owner, desired_plan):
        """
        Takes an owner and desired plan, and updates the owner's plan. Depending
        on current state, might create a stripe checkout session and return
        the checkout session's ID, which is a string. Otherwise returns None.
        """
        print("Testing - update_plan")
        if desired_plan["value"] == "users-free":
            if owner.stripe_subscription_id is not None:
                self.payment_service.delete_subscription(owner)
            else:
                owner.set_free_plan()
        elif desired_plan["value"] in PR_AUTHOR_PAID_USER_PLAN_REPRESENTATIONS:
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
