import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import stripe
from dateutil.relativedelta import relativedelta
from django.conf import settings
from shared.plan.constants import PlanBillingRate, TierName
from shared.plan.service import PlanService

from billing.constants import REMOVED_INVOICE_STATUSES
from codecov_auth.models import Owner, Plan

log = logging.getLogger(__name__)

SCHEDULE_RELEASE_OFFSET = 10

if settings.STRIPE_API_KEY:
    stripe.api_key = settings.STRIPE_API_KEY
    stripe.api_version = "2024-12-18.acacia"


def _log_stripe_error(method):
    def catch_and_raise(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except stripe.StripeError as e:
            log.warning(f"StripeError raised: {e.user_message}")
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
    def update_email_address(self, owner, email_address):
        pass

    @abstractmethod
    def update_billing_address(self, owner, name, billing_address):
        pass

    @abstractmethod
    def get_schedule(self, owner):
        pass

    @abstractmethod
    def apply_cancellation_discount(self, owner: Owner):
        pass

    @abstractmethod
    def create_setup_intent(self, owner):
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

    def _get_checkout_session_and_subscription_metadata(self, owner: Owner):
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
        except stripe.InvalidRequestError:
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
    def list_filtered_invoices(self, owner: Owner, limit=10):
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

    def cancel_and_refund(
        self,
        owner,
        current_subscription_datetime,
        subscription_plan_interval,
        autorefunds_remaining,
    ):
        # cancels a Stripe customer subscription immediately and attempts to refund their payments for the current period
        stripe.Subscription.cancel(owner.stripe_subscription_id)

        start_of_last_period = current_subscription_datetime - relativedelta(months=1)
        invoice_grace_period_start = current_subscription_datetime - relativedelta(
            days=1
        )

        if subscription_plan_interval == "year":
            start_of_last_period = current_subscription_datetime - relativedelta(
                years=1
            )
            invoice_grace_period_start = current_subscription_datetime - relativedelta(
                days=3
            )

        invoices_list = stripe.Invoice.list(
            subscription=owner.stripe_subscription_id,
            status="paid",
            created={
                "gte": int(start_of_last_period.timestamp()),
                "lt": int(current_subscription_datetime.timestamp()),
            },
        )

        # we only want to refund the invoices PAID recently for the latest, current period. "invoices_list" gives us any invoice
        # created over the last month/year based on what period length they are on but the customer could have possibly
        # switched from monthly to yearly recently.
        recently_paid_invoices_list = [
            invoice
            for invoice in invoices_list["data"]
            if invoice["status_transitions"]["paid_at"] is not None
            and invoice["status_transitions"]["paid_at"]
            >= int(invoice_grace_period_start.timestamp())
        ]

        created_refund = False
        # there could be multiple invoices that need to be refunded such as if the user increased seats within the grace period
        for invoice in recently_paid_invoices_list:
            # refund if the invoice has a charge and it has been fully paid
            if invoice["charge"] is not None and invoice["amount_remaining"] == 0:
                stripe.Refund.create(invoice["charge"])
                created_refund = True

        if created_refund:
            # update the customer's balance back to 0 in accordance to
            # https://support.stripe.com/questions/refunding-credit-balance-to-customer-after-subscription-downgrade-or-cancellation
            stripe.Customer.modify(
                owner.stripe_customer_id,
                balance=0,
                metadata={"autorefunds_remaining": str(autorefunds_remaining - 1)},
            )
            log.info(
                "Grace period cancelled a subscription and autorefunded associated invoices",
                extra=dict(
                    owner_id=owner.ownerid,
                    user_id=self.requesting_user.ownerid,
                    subscription_id=owner.stripe_subscription_id,
                    customer_id=owner.stripe_customer_id,
                    autorefunds_remaining=autorefunds_remaining - 1,
                ),
            )
        else:
            log.info(
                "Grace period cancelled a subscription but did not find any appropriate invoices to autorefund",
                extra=dict(
                    owner_id=owner.ownerid,
                    user_id=self.requesting_user.ownerid,
                    subscription_id=owner.stripe_subscription_id,
                    customer_id=owner.stripe_customer_id,
                    autorefunds_remaining=autorefunds_remaining,
                ),
            )

    @_log_stripe_error
    def delete_subscription(self, owner: Owner):
        subscription = stripe.Subscription.retrieve(owner.stripe_subscription_id)
        subscription_schedule_id = subscription.schedule

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

        # we give an auto-refund grace period of 24 hours for a monthly subscription or 72 hours for a yearly subscription
        current_subscription_datetime = datetime.fromtimestamp(
            subscription["current_period_start"], tz=timezone.utc
        )
        difference_from_now = datetime.now(timezone.utc) - current_subscription_datetime

        subscription_plan_interval = getattr(
            getattr(subscription, "plan", None), "interval", None
        )
        within_refund_grace_period = (
            subscription_plan_interval == "month" and difference_from_now.days < 1
        ) or (subscription_plan_interval == "year" and difference_from_now.days < 3)

        if within_refund_grace_period:
            customer = stripe.Customer.retrieve(owner.stripe_customer_id)
            # we are currently allowing customers 2 autorefund instances
            autorefunds_remaining = int(
                customer["metadata"].get("autorefunds_remaining", "2")
            )
            log.info(
                "Deleting subscription with attempted immediate cancellation with autorefund within grace period",
                extra=dict(
                    owner_id=owner.ownerid,
                    user_id=self.requesting_user.ownerid,
                    subscription_id=owner.stripe_subscription_id,
                    customer_id=owner.stripe_customer_id,
                    autorefunds_remaining=autorefunds_remaining,
                ),
            )
            if autorefunds_remaining > 0:
                return self.cancel_and_refund(
                    owner,
                    current_subscription_datetime,
                    subscription_plan_interval,
                    autorefunds_remaining,
                )

        # schedule a cancellation at the end of the paid period with no refund
        stripe.Subscription.modify(
            owner.stripe_subscription_id,
            cancel_at_period_end=True,
            proration_behavior="none",
        )

    @_log_stripe_error
    def get_subscription(self, owner: Owner):
        if not owner.stripe_subscription_id:
            return None
        return stripe.Subscription.retrieve(
            owner.stripe_subscription_id,
            expand=[
                "latest_invoice",
                "customer",
                "customer.invoice_settings.default_payment_method",
                "customer.tax_ids",
            ],
        )

    @_log_stripe_error
    def get_schedule(self, owner: Owner):
        if not owner.stripe_subscription_id:
            return None

        subscription = self.get_subscription(owner)
        subscription_schedule_id = subscription.schedule

        if not subscription_schedule_id:
            return None

        return stripe.SubscriptionSchedule.retrieve(subscription_schedule_id)

    @_log_stripe_error
    def modify_subscription(self, owner: Owner, desired_plan: dict):
        desired_plan_info = Plan.objects.filter(name=desired_plan["value"]).first()
        if not desired_plan_info:
            log.error(
                f"Plan {desired_plan['value']} not found",
                extra=dict(owner_id=owner.ownerid),
            )
            return

        subscription = stripe.Subscription.retrieve(owner.stripe_subscription_id)
        proration_behavior = self._get_proration_params(
            owner,
            desired_plan_info=desired_plan_info,
            desired_quantity=desired_plan["quantity"],
        )
        subscription_schedule_id = subscription.schedule

        # proration_behavior indicates whether we immediately invoice a user or not. We only immediately
        # invoice a user if the user increases the number of seats or if the plan changes from monthly to yearly.
        # An increase in seats and/or plan implies the user is upgrading, hence 'is_upgrading' is a consequence
        # of proration_behavior providing an invoice, in this case, != "none"
        # TODO: change this to "self._is_upgrading_seats(owner, desired_plan) or self._is_extending_term(owner, desired_plan)"
        is_upgrading = (
            True
            if proration_behavior != "none" and desired_plan_info.stripe_id
            else False
        )

        # Divide logic bw immediate updates and scheduled updates
        # Immediate updates: when user upgrades seats or plan
        #   If the user is not in a schedule, update immediately
        #   If the user is in a schedule, update the existing schedule
        # Scheduled updates: when the user decreases seats or plan
        #   If the user is not in a schedule, create a schedule
        #   If the user is in a schedule, update the existing schedule
        if is_upgrading:
            if subscription_schedule_id:
                log.info(
                    f"Releasing Stripe schedule for owner {owner.ownerid} to {desired_plan['value']} with {desired_plan['quantity']} seats by user #{self.requesting_user.ownerid}"
                )
                stripe.SubscriptionSchedule.release(subscription_schedule_id)
            log.info(
                f"Updating Stripe subscription for owner {owner.ownerid} to {desired_plan['value']} by user #{self.requesting_user.ownerid}"
            )

            subscription = stripe.Subscription.modify(
                owner.stripe_subscription_id,
                cancel_at_period_end=False,
                items=[
                    {
                        "id": subscription["items"]["data"][0]["id"],
                        "plan": desired_plan_info.stripe_id,
                        "quantity": desired_plan["quantity"],
                    }
                ],
                metadata=self._get_checkout_session_and_subscription_metadata(owner),
                proration_behavior=proration_behavior,
                # TODO: we need to include this arg, but it means we need to remove some of the existing args
                # on the .modify() call https://docs.stripe.com/billing/subscriptions/pending-updates-reference
                # payment_behavior="pending_if_incomplete",
            )
            log.info(
                f"Stripe subscription upgrade attempted for owner {owner.ownerid} by user #{self.requesting_user.ownerid}"
            )
            indication_of_payment_failure = getattr(
                subscription, "pending_update", None
            )
            if indication_of_payment_failure:
                # payment failed, raise this to user by setting as delinquent
                owner.delinquent = True
                owner.save()
                log.info(
                    f"Stripe subscription upgrade failed for owner {owner.ownerid} by user #{self.requesting_user.ownerid}",
                    extra=dict(pending_update=indication_of_payment_failure),
                )
            else:
                # payment successful
                plan_service = PlanService(current_org=owner)
                plan_service.update_plan(
                    name=desired_plan["value"], user_count=desired_plan["quantity"]
                )
                log.info(
                    f"Stripe subscription upgraded successfully for owner {owner.ownerid} by user #{self.requesting_user.ownerid}"
                )
        else:
            if not subscription_schedule_id:
                schedule = stripe.SubscriptionSchedule.create(
                    from_subscription=owner.stripe_subscription_id
                )
                subscription_schedule_id = schedule.id
            self._modify_subscription_schedule(
                owner, subscription, subscription_schedule_id, desired_plan
            )

    def _modify_subscription_schedule(
        self,
        owner: Owner,
        subscription: stripe.Subscription,
        subscription_schedule_id: str,
        desired_plan: dict,
    ):
        current_subscription_start_date = subscription["current_period_start"]
        current_subscription_end_date = subscription["current_period_end"]

        subscription_item = subscription["items"]["data"][0]
        current_plan = subscription_item["plan"]["id"]
        current_quantity = subscription_item["quantity"]

        plan = Plan.objects.filter(name=desired_plan["value"]).first()
        if not plan or not plan.stripe_id:
            log.error(
                f"Plan {desired_plan['value']} not found",
                extra=dict(owner_id=owner.ownerid),
            )
            return

        stripe.SubscriptionSchedule.modify(
            subscription_schedule_id,
            end_behavior="release",
            phases=[
                {
                    "start_date": current_subscription_start_date,
                    "end_date": current_subscription_end_date,
                    "items": [
                        {
                            "plan": current_plan,
                            "price": current_plan,
                            "quantity": current_quantity,
                        }
                    ],
                    "proration_behavior": "none",
                },
                {
                    "start_date": current_subscription_end_date,
                    "end_date": current_subscription_end_date + SCHEDULE_RELEASE_OFFSET,
                    "items": [
                        {
                            "plan": plan.stripe_id,
                            "price": plan.stripe_id,
                            "quantity": desired_plan["quantity"],
                        }
                    ],
                    "proration_behavior": "none",
                },
            ],
            metadata=self._get_checkout_session_and_subscription_metadata(owner),
        )

    def _is_upgrading_seats(self, owner: Owner, desired_quantity: int) -> bool:
        """
        Returns `True` if purchasing more seats.
        """
        return bool(owner.plan_user_count and owner.plan_user_count < desired_quantity)

    def _is_extending_term(
        self, current_plan_info: Plan, desired_plan_info: Plan
    ) -> bool:
        """
        Returns `True` if switching from monthly to yearly plan.
        """

        return bool(
            current_plan_info
            and current_plan_info.billing_rate == PlanBillingRate.MONTHLY.value
            and desired_plan_info
            and desired_plan_info.billing_rate == PlanBillingRate.YEARLY.value
        )

    def _is_similar_plan(
        self,
        owner: Owner,
        current_plan_info: Plan,
        desired_plan_info: Plan,
        desired_quantity: int,
    ) -> bool:
        """
        Returns `True` if switching to a plan with similar term and seats.
        """
        is_same_term = (
            current_plan_info
            and desired_plan_info
            and current_plan_info.billing_rate == desired_plan_info.billing_rate
        )

        is_same_seats = (
            owner.plan_user_count and owner.plan_user_count == desired_quantity
        )
        # If from PRO to TEAM, then not a similar plan
        if (
            current_plan_info.tier.tier_name != TierName.TEAM.value
            and desired_plan_info.tier.tier_name == TierName.TEAM.value
        ):
            return False
        # If from TEAM to PRO, then considered a similar plan but really is an upgrade
        elif (
            current_plan_info.tier.tier_name == TierName.TEAM.value
            and desired_plan_info.tier.tier_name != TierName.TEAM.value
        ):
            return True

        return bool(is_same_term and is_same_seats)

    def _get_proration_params(
        self, owner: Owner, desired_plan_info: Plan, desired_quantity: int
    ) -> str:
        current_plan_info = Plan.objects.select_related("tier").get(name=owner.plan)
        if (
            self._is_upgrading_seats(owner=owner, desired_quantity=desired_quantity)
            or self._is_extending_term(
                current_plan_info=current_plan_info, desired_plan_info=desired_plan_info
            )
            or self._is_similar_plan(
                owner=owner,
                current_plan_info=current_plan_info,
                desired_plan_info=desired_plan_info,
                desired_quantity=desired_quantity,
            )
        ):
            return "always_invoice"
        else:
            return "none"

    def _get_success_and_cancel_url(self, owner: Owner):
        short_services = {"github": "gh", "bitbucket": "bb", "gitlab": "gl"}
        base_path = f"/plan/{short_services[owner.service]}/{owner.username}"
        success_url = f"{settings.CODECOV_DASHBOARD_URL}{base_path}?success"
        cancel_url = f"{settings.CODECOV_DASHBOARD_URL}{base_path}?cancel"
        return success_url, cancel_url

    @_log_stripe_error
    def create_checkout_session(self, owner: Owner, desired_plan: dict):
        success_url, cancel_url = self._get_success_and_cancel_url(owner)
        log.info(
            "Creating Stripe Checkout Session for owner",
            extra=dict(owner_id=owner.ownerid),
        )

        plan = Plan.objects.filter(name=desired_plan["value"]).first()
        if not plan or not plan.stripe_id:
            log.error(
                f"Plan {desired_plan['value']} not found",
                extra=dict(owner_id=owner.ownerid),
            )
            return

        session = stripe.checkout.Session.create(
            payment_method_configuration=settings.STRIPE_PAYMENT_METHOD_CONFIGURATION_ID,
            billing_address_collection="required",
            payment_method_collection="if_required",
            client_reference_id=str(owner.ownerid),
            success_url=success_url,
            cancel_url=cancel_url,
            customer=owner.stripe_customer_id,
            mode="subscription",
            line_items=[
                {
                    "price": plan.stripe_id,
                    "quantity": desired_plan["quantity"],
                }
            ],
            subscription_data={
                "metadata": self._get_checkout_session_and_subscription_metadata(owner),
            },
            tax_id_collection={"enabled": True},
            customer_update=(
                {"name": "auto", "address": "auto"}
                if owner.stripe_customer_id
                else None
            ),
        )
        log.info(
            f"Stripe Checkout Session created successfully for owner {owner.ownerid} by user #{self.requesting_user.ownerid}"
        )
        return session["id"]

    def _is_unverified_payment_method(self, payment_method_id: str) -> bool:
        payment_method = stripe.PaymentMethod.retrieve(payment_method_id)

        is_us_bank_account = payment_method.type == "us_bank_account" and hasattr(
            payment_method, "us_bank_account"
        )
        if is_us_bank_account:
            setup_intents = stripe.SetupIntent.list(
                payment_method=payment_method_id, limit=1
            )

            try:
                latest_intent = setup_intents.data[0]
                if (
                    latest_intent.status == "requires_action"
                    and latest_intent.next_action
                    and latest_intent.next_action.type == "verify_with_microdeposits"
                ):
                    return True
            except Exception as e:
                log.error(
                    "Error retrieving latest setup intent",
                    payment_method_id=payment_method_id,
                    extra=dict(error=e),
                )
                return False

        return False

    @_log_stripe_error
    def update_payment_method(self, owner: Owner, payment_method: str) -> None:
        log.info(
            "Stripe update payment method for owner",
            extra=dict(
                owner_id=owner.ownerid,
                user_id=self.requesting_user.ownerid,
                subscription_id=owner.stripe_subscription_id,
                customer_id=owner.stripe_customer_id,
            ),
        )
        if owner.stripe_subscription_id is None or owner.stripe_customer_id is None:
            log.warn(
                "Missing subscription or customer id, returning early",
                extra=dict(
                    owner_id=owner.ownerid,
                    subscription_id=owner.stripe_subscription_id,
                    customer_id=owner.stripe_customer_id,
                ),
            )
            return None

        # do not set as default if the new payment method is unverified (e.g., awaiting microdeposits)
        should_set_as_default = not self._is_unverified_payment_method(payment_method)

        if should_set_as_default:
            stripe.PaymentMethod.attach(
                payment_method, customer=owner.stripe_customer_id
            )
            stripe.Customer.modify(
                owner.stripe_customer_id,
                invoice_settings={"default_payment_method": payment_method},
            )
            stripe.Subscription.modify(
                owner.stripe_subscription_id, default_payment_method=payment_method
            )
        log.info(
            f"Successfully updated payment method for owner {owner.ownerid} by user #{self.requesting_user.ownerid}",
            extra=dict(
                owner_id=owner.ownerid,
                user_id=self.requesting_user.ownerid,
                subscription_id=owner.stripe_subscription_id,
                customer_id=owner.stripe_customer_id,
            ),
        )

    @_log_stripe_error
    def update_email_address(
        self,
        owner: Owner,
        email_address: str,
        apply_to_default_payment_method: bool = False,
    ):
        if not re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email_address):
            return None

        log.info(f"Stripe update email address for owner {owner.ownerid}")
        if owner.stripe_subscription_id is None:
            log.info(
                f"stripe_subscription_id is None, not updating stripe email for owner {owner.ownerid}"
            )
            return None
        stripe.Customer.modify(owner.stripe_customer_id, email=email_address)
        log.info(
            f"Stripe successfully updated email address for owner {owner.ownerid} by user #{self.requesting_user.ownerid}"
        )

        if apply_to_default_payment_method:
            try:
                default_payment_method = stripe.Customer.retrieve(
                    owner.stripe_customer_id
                )["invoice_settings"]["default_payment_method"]

                stripe.PaymentMethod.modify(
                    default_payment_method,
                    billing_details={"email": email_address},
                )
                log.info(
                    "Stripe successfully updated billing email for payment method",
                    extra=dict(
                        payment_method=default_payment_method,
                        stripe_customer_id=owner.stripe_customer_id,
                        ownerid=owner.ownerid,
                    ),
                )
            except Exception as e:
                log.error(
                    "Unable to update billing email for payment method",
                    extra=dict(
                        payment_method=default_payment_method,
                        stripe_customer_id=owner.stripe_customer_id,
                        error=str(e),
                        ownerid=owner.ownerid,
                    ),
                )

    @_log_stripe_error
    def update_billing_address(self, owner: Owner, name, billing_address):
        log.info(f"Stripe update billing address for owner {owner.ownerid}")
        if owner.stripe_customer_id is None:
            log.info(
                f"stripe_customer_id is None, cannot update default billing address for owner {owner.ownerid}"
            )
            return None

        try:
            default_payment_method = stripe.Customer.retrieve(
                owner.stripe_customer_id
            ).invoice_settings.default_payment_method

            stripe.PaymentMethod.modify(
                default_payment_method,
                billing_details={"name": name, "address": billing_address},
            )

            stripe.Customer.modify(owner.stripe_customer_id, address=billing_address)
            log.info(
                f"Stripe successfully updated billing address for owner {owner.ownerid} by user #{self.requesting_user.ownerid}"
            )
        except Exception:
            log.error(
                "Unable to update billing address for customer",
                extra=dict(
                    customer_id=owner.stripe_customer_id,
                    subscription_id=owner.stripe_subscription_id,
                ),
            )

    @_log_stripe_error
    def apply_cancellation_discount(self, owner: Owner):
        if owner.stripe_subscription_id is None:
            log.info(
                f"stripe_subscription_id is None, not applying cancellation coupon for owner {owner.ownerid}"
            )
            return
        plan_service = PlanService(current_org=owner)
        billing_rate = plan_service.billing_rate

        if billing_rate == PlanBillingRate.MONTHLY.value and not owner.stripe_coupon_id:
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
                    "email": owner.email,
                    "name": owner.name,
                },
            )

            owner.stripe_coupon_id = coupon.id
            owner.save()

            log.info(
                f"Applying cancellation coupon to Stripe subscription for owner {owner.ownerid}"
            )
            stripe.Customer.modify(
                owner.stripe_customer_id,
                coupon=owner.stripe_coupon_id,
            )

    @_log_stripe_error
    def create_setup_intent(self, owner: Owner) -> stripe.SetupIntent:
        log.info(
            "Stripe create setup intent for owner",
            extra=dict(
                owner_id=owner.ownerid,
                requesting_user_id=self.requesting_user.ownerid,
                subscription_id=owner.stripe_subscription_id,
                customer_id=owner.stripe_customer_id,
            ),
        )
        return stripe.SetupIntent.create(
            payment_method_configuration=settings.STRIPE_PAYMENT_METHOD_CONFIGURATION_ID,
            customer=owner.stripe_customer_id,
        )

    @_log_stripe_error
    def get_unverified_payment_methods(self, owner: Owner):
        log.info(
            "Getting unverified payment methods",
            extra=dict(
                owner_id=owner.ownerid, stripe_customer_id=owner.stripe_customer_id
            ),
        )
        if not owner.stripe_customer_id:
            return []

        unverified_payment_methods = []

        # Check payment intents
        has_more = True
        starting_after = None
        while has_more:
            payment_intents = stripe.PaymentIntent.list(
                customer=owner.stripe_customer_id,
                limit=20,
                starting_after=starting_after,
            )
            for intent in payment_intents.data or []:
                if (
                    intent.get("next_action")
                    and intent.next_action
                    and intent.next_action.get("type") == "verify_with_microdeposits"
                ):
                    unverified_payment_methods.extend(
                        [
                            {
                                "payment_method_id": intent.payment_method,
                                "hosted_verification_url": intent.next_action.verify_with_microdeposits.hosted_verification_url,
                            }
                        ]
                    )
            has_more = payment_intents.has_more
            if has_more and payment_intents.data:
                starting_after = payment_intents.data[-1].id

        # Check setup intents
        has_more = True
        starting_after = None
        while has_more:
            setup_intents = stripe.SetupIntent.list(
                customer=owner.stripe_customer_id,
                limit=20,
                starting_after=starting_after,
            )
            for intent in setup_intents.data:
                if (
                    intent.get("next_action")
                    and intent.next_action
                    and intent.next_action.get("type") == "verify_with_microdeposits"
                ):
                    unverified_payment_methods.extend(
                        [
                            {
                                "payment_method_id": intent.payment_method,
                                "hosted_verification_url": intent.next_action.verify_with_microdeposits.hosted_verification_url,
                            }
                        ]
                    )
            has_more = setup_intents.has_more
            if has_more and setup_intents.data:
                starting_after = setup_intents.data[-1].id

        return unverified_payment_methods


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

    def update_email_address(self, owner, email_address):
        pass

    def update_billing_address(self, owner, name, billing_address):
        pass

    def get_schedule(self, owner):
        pass

    def apply_cancellation_discount(self, owner: Owner):
        pass

    def create_setup_intent(self, owner):
        pass

    def get_unverified_payment_methods(self, owner: Owner):
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

    def get_unverified_payment_methods(self, owner: Owner):
        return self.payment_service.get_unverified_payment_methods(owner)

    def update_plan(self, owner, desired_plan):
        """
        Takes an owner and desired plan, and updates the owner's plan. Depending
        on current state, might create a stripe checkout session and return
        the checkout session's ID, which is a string. Otherwise returns None.
        """
        try:
            plan = Plan.objects.get(name=desired_plan["value"])
        except Plan.DoesNotExist:
            log.warning(
                f"Unable to find plan {desired_plan['value']} for owner {owner.ownerid}"
            )
            return None

        if not plan.is_active:
            log.warning(
                f"Attempted to transition to non-existent or legacy plan: "
                f"owner {owner.ownerid}, plan: {desired_plan}"
            )
            return None

        if plan.paid_plan is False:
            if owner.stripe_subscription_id is not None:
                self.payment_service.delete_subscription(owner)
            else:
                plan_service = PlanService(current_org=owner)
                plan_service.set_default_plan_data()
        else:
            if owner.stripe_subscription_id is not None:
                # if the existing subscription is incomplete, clean it up and create a new checkout session
                subscription = self.payment_service.get_subscription(owner)

                if subscription and subscription.status == "incomplete":
                    self._cleanup_incomplete_subscription(subscription, owner)
                    return self.payment_service.create_checkout_session(
                        owner, desired_plan
                    )

                # if the existing subscription is complete, modify the plan
                self.payment_service.modify_subscription(owner, desired_plan)
            else:
                # if the owner has no subscription, create a new checkout session
                return self.payment_service.create_checkout_session(owner, desired_plan)

    def update_payment_method(self, owner, payment_method):
        """
        Takes an owner and a new card. card is an object coming directly from
        the front-end; without any validation, as payment service can handle
        the card data differently
        """
        return self.payment_service.update_payment_method(owner, payment_method)

    def update_email_address(
        self,
        owner: Owner,
        email_address: str,
        apply_to_default_payment_method: bool = False,
    ):
        """
        Takes an owner and a new email. Email is a string coming directly from
        the front-end. If the owner has a payment id and if it's a valid email,
        the payment service will update the email address in the upstream service.
        Otherwise returns None.
        """
        return self.payment_service.update_email_address(
            owner, email_address, apply_to_default_payment_method
        )

    def update_billing_address(self, owner: Owner, name: str, billing_address):
        """
        Takes an owner and a billing address. Try to update the owner's billing address
        to the address passed in. Address should be validated via stripe component prior
        to hitting this service method. Return None if invalid.
        """
        return self.payment_service.update_billing_address(owner, name, billing_address)

    def apply_cancellation_discount(self, owner: Owner):
        return self.payment_service.apply_cancellation_discount(owner)

    def create_setup_intent(self, owner: Owner):
        """
        Creates a SetupIntent for the given owner to securely collect payment details
        See https://docs.stripe.com/api/setup_intents/create
        """
        return self.payment_service.create_setup_intent(owner)

    def _cleanup_incomplete_subscription(
        self, subscription: stripe.Subscription, owner: Owner
    ):
        try:
            payment_intent_id = subscription.latest_invoice.payment_intent
        except Exception as e:
            log.error(
                "Latest invoice is missing payment intent id",
                extra=dict(error=e),
            )
            return None

        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        if payment_intent.status == "requires_action":
            log.info(
                "Subscription has pending payment verification",
                extra=dict(
                    subscription_id=subscription.get("id"),
                    payment_intent_id=payment_intent.get("id"),
                    payment_intent_status=payment_intent.get("status"),
                ),
            )
            try:
                # Delete the subscription, which also removes the
                # pending payment method and unverified payment intent
                stripe.Subscription.delete(subscription)
                log.info(
                    "Deleted incomplete subscription",
                    extra=dict(
                        subscription_id=subscription.get("id"),
                        payment_intent_id=payment_intent.get("id"),
                    ),
                )
            except Exception as e:
                log.error(
                    "Failed to delete subscription",
                    extra=dict(
                        subscription_id=subscription.get("id"),
                        payment_intent_id=payment_intent.get("id"),
                        error=str(e),
                    ),
                )
