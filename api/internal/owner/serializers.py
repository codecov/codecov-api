import logging
from dataclasses import asdict
from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.conf import settings
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from codecov_auth.models import Owner
from plan.constants import (
    PAID_PLANS,
    SENTRY_PAID_USER_PLAN_REPRESENTATIONS,
    TEAM_PLAN_MAX_USERS,
    TEAM_PLAN_REPRESENTATIONS,
)
from plan.service import PlanService
from services.billing import BillingService
from services.sentry import send_user_webhook as send_sentry_webhook

log = logging.getLogger(__name__)


class OwnerSerializer(serializers.ModelSerializer):
    stats = serializers.SerializerMethodField()

    class Meta:
        model = Owner
        fields = (
            "avatar_url",
            "service",
            "username",
            "name",
            "stats",
            "ownerid",
            "integration_id",
        )

        read_only_fields = fields

    def get_stats(self, obj):
        if obj.cache and "stats" in obj.cache:
            return obj.cache["stats"]


class StripeLineItemSerializer(serializers.Serializer):
    description = serializers.CharField()
    amount = serializers.FloatField()
    currency = serializers.CharField()
    period = serializers.JSONField()
    plan_name = serializers.SerializerMethodField()
    quantity = serializers.IntegerField()

    def get_plan_name(self, line_item):
        plan = line_item.get("plan")
        if plan:
            return plan.get("name")


class StripeInvoiceSerializer(serializers.Serializer):
    id = serializers.CharField()
    number = serializers.CharField()
    status = serializers.CharField()
    created = serializers.IntegerField()
    period_start = serializers.IntegerField()
    period_end = serializers.IntegerField()
    due_date = serializers.IntegerField()
    customer_name = serializers.CharField()
    customer_address = serializers.CharField()
    currency = serializers.CharField()
    amount_paid = serializers.FloatField()
    amount_due = serializers.FloatField()
    amount_remaining = serializers.FloatField()
    total = serializers.FloatField()
    subtotal = serializers.FloatField()
    invoice_pdf = serializers.CharField()
    line_items = StripeLineItemSerializer(many=True, source="lines.data")
    footer = serializers.CharField()
    customer_email = serializers.CharField()
    customer_shipping = serializers.CharField()


class StripeDiscountSerializer(serializers.Serializer):
    name = serializers.CharField(source="coupon.name")
    percent_off = serializers.FloatField(source="coupon.percent_off")
    duration_in_months = serializers.IntegerField(source="coupon.duration_in_months")
    expires = serializers.SerializerMethodField()

    def get_expires(self, customer):
        coupon = customer.get("coupon")
        if coupon:
            months = coupon.get("duration_in_months")
            created = coupon.get("created")
            if months and created:
                expires = datetime.fromtimestamp(created) + relativedelta(months=months)
                return int(expires.timestamp())


class StripeCustomerSerializer(serializers.Serializer):
    id = serializers.CharField()
    discount = StripeDiscountSerializer()
    email = serializers.CharField()


class StripeCardSerializer(serializers.Serializer):
    brand = serializers.CharField()
    exp_month = serializers.IntegerField()
    exp_year = serializers.IntegerField()
    last4 = serializers.CharField()


class StripePaymentMethodSerializer(serializers.Serializer):
    card = StripeCardSerializer(read_only=True)
    billing_details = serializers.JSONField(read_only=True)


class PlanSerializer(serializers.Serializer):
    marketing_name = serializers.CharField(read_only=True)
    value = serializers.CharField()
    billing_rate = serializers.CharField(read_only=True)
    base_unit_price = serializers.IntegerField(read_only=True)
    benefits = serializers.JSONField(read_only=True)
    quantity = serializers.IntegerField(required=False)

    def validate_value(self, value):
        current_org = self.context["view"].owner
        current_owner = self.context["request"].current_owner

        plan_service = PlanService(current_org=current_org)
        available_plans = [
            asdict(plan) for plan in plan_service.available_plans(current_owner)
        ]
        plan_values = [plan["value"] for plan in available_plans]
        if value not in plan_values:
            if value in SENTRY_PAID_USER_PLAN_REPRESENTATIONS:
                log.warning(
                    "Non-Sentry user attempted to transition to Sentry plan",
                    extra=dict(owner_id=current_owner.pk, plan=value),
                )
            raise serializers.ValidationError(
                f"Invalid value for plan: {value}; " f"must be one of {plan_values}"
            )
        return value

    def validate(self, plan):
        owner = self.context["view"].owner

        # Validate quantity here because we need access to whole plan object
        if plan["value"] in PAID_PLANS:
            if "quantity" not in plan:
                raise serializers.ValidationError(
                    "Field 'quantity' required for updating to paid plans"
                )
            if plan["quantity"] <= 1:
                raise serializers.ValidationError(
                    "Quantity for paid plan must be greater than 1"
                )

            plan_service = PlanService(current_org=owner)
            is_org_trialing = plan_service.is_org_trialing

            if plan["quantity"] < owner.activated_user_count and not is_org_trialing:
                raise serializers.ValidationError(
                    "Quantity cannot be lower than currently activated user count"
                )
            if (
                plan["quantity"] == owner.plan_user_count
                and plan["value"] == owner.plan
                and not is_org_trialing
            ):
                raise serializers.ValidationError(
                    "Quantity or plan for paid plan must be different from the existing one"
                )
            if (
                plan["value"] in TEAM_PLAN_REPRESENTATIONS
                and plan["quantity"] > TEAM_PLAN_MAX_USERS
            ):
                raise serializers.ValidationError(
                    f"Quantity for Team plan cannot exceed {TEAM_PLAN_MAX_USERS}"
                )
        return plan


class SubscriptionDetailSerializer(serializers.Serializer):
    latest_invoice = StripeInvoiceSerializer()
    default_payment_method = StripePaymentMethodSerializer(
        source="customer.invoice_settings.default_payment_method"
    )
    cancel_at_period_end = serializers.BooleanField()
    current_period_end = serializers.IntegerField()
    customer = StripeCustomerSerializer()
    collection_method = serializers.CharField()
    trial_end = serializers.IntegerField()


class StripeScheduledPhaseSerializer(serializers.Serializer):
    start_date = serializers.IntegerField()
    plan = serializers.SerializerMethodField()
    quantity = serializers.SerializerMethodField()

    def get_plan(self, phase):
        plan_id = phase["items"][0]["plan"]
        stripe_plan_dict = settings.STRIPE_PLAN_IDS
        plan_name = list(stripe_plan_dict.keys())[
            list(stripe_plan_dict.values()).index(plan_id)
        ]
        marketing_plan_name = PAID_PLANS[plan_name].billing_rate
        return marketing_plan_name

    def get_quantity(self, phase):
        return phase["items"][0]["quantity"]


class ScheduleDetailSerializer(serializers.Serializer):
    id = serializers.CharField()
    scheduled_phase = serializers.SerializerMethodField()

    def get_scheduled_phase(self, schedule):
        if len(schedule["phases"]) > 1:
            return StripeScheduledPhaseSerializer(schedule["phases"][-1]).data
        else:
            # This error represents the phases object not having 2 phases; we are interested in the 2nd entry within phases
            # since it represents the scheduled phase
            log.error(
                "Expecting schedule object to have 2 phases, returning None",
                extra=dict(
                    ownerid=schedule.metadata.obo_organization,
                    requesting_user_id=schedule.metadata.obo,
                ),
            )
            return None


class RootOrganizationSerializer(serializers.Serializer):
    """
    Minimalist serializer to expose the root organization of a sub group
    so we can expose the minimal data required for the UI while hiding data
    that might only be for admin (invoice, billing data, etc)
    """

    username = serializers.CharField()
    plan = PlanSerializer(source="pretty_plan")


class AccountDetailsSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(source="pretty_plan")
    checkout_session_id = serializers.SerializerMethodField()
    subscription_detail = serializers.SerializerMethodField()
    root_organization = RootOrganizationSerializer()
    schedule_detail = serializers.SerializerMethodField()
    apply_cancellation_discount = serializers.BooleanField(write_only=True)

    class Meta:
        model = Owner

        read_only_fields = ("integration_id",)

        fields = read_only_fields + (
            "activated_student_count",
            "activated_user_count",
            "checkout_session_id",
            "email",
            "inactive_user_count",
            "name",
            "nb_active_private_repos",
            "plan",
            "plan_auto_activate",
            "plan_provider",
            "uses_invoice",
            "repo_total_credits",
            "root_organization",
            "schedule_detail",
            "student_count",
            "subscription_detail",
            "apply_cancellation_discount",
        )

    def _get_billing(self):
        current_owner = self.context["request"].current_owner
        return BillingService(requesting_user=current_owner)

    def get_subscription_detail(self, owner):
        subscription_detail = self._get_billing().get_subscription(owner)
        if subscription_detail:
            return SubscriptionDetailSerializer(subscription_detail).data

    def get_schedule_detail(self, owner):
        schedule_detail = self._get_billing().get_schedule(owner)
        if schedule_detail:
            return ScheduleDetailSerializer(schedule_detail).data

    def get_checkout_session_id(self, _):
        return self.context.get("checkout_session_id")

    def update(self, instance, validated_data):
        if "pretty_plan" in validated_data:
            desired_plan = validated_data.pop("pretty_plan")
            checkout_session_id_or_none = self._get_billing().update_plan(
                instance, desired_plan
            )

            if desired_plan["value"] in SENTRY_PAID_USER_PLAN_REPRESENTATIONS:
                current_owner = self.context["view"].request.current_owner
                send_sentry_webhook(current_owner, instance)

            if checkout_session_id_or_none is not None:
                self.context["checkout_session_id"] = checkout_session_id_or_none

        if validated_data.get("apply_cancellation_discount") is True:
            self._get_billing().apply_cancellation_discount(instance)

        super().update(instance, validated_data)
        return self.context["view"].get_object()


class UserSerializer(serializers.ModelSerializer):
    activated = serializers.BooleanField()
    is_admin = serializers.BooleanField()
    last_pull_timestamp = serializers.SerializerMethodField()

    class Meta:
        model = Owner
        fields = (
            "activated",
            "is_admin",
            "username",
            "email",
            "ownerid",
            "student",
            "name",
            "last_pull_timestamp",
        )

    def update(self, instance, validated_data):
        owner = self.context["view"].owner

        if "activated" in validated_data:
            if validated_data["activated"] is True and owner.can_activate_user(
                instance
            ):
                owner.activate_user(instance)
            elif validated_data["activated"] is False:
                owner.deactivate_user(instance)
            else:
                raise PermissionDenied(
                    f"Cannot activate user {instance.username} -- not enough seats left."
                )

        if "is_admin" in validated_data:
            if validated_data["is_admin"]:
                owner.add_admin(instance)
            else:
                owner.remove_admin(instance)

        # Re-fetch from DB to set activated and admin fields
        return self.context["view"].get_object()

    def get_last_pull_timestamp(self, obj):
        # this field comes from an annotation that may not always be applied to the queryset
        if hasattr(obj, "last_pull_timestamp"):
            return obj.last_pull_timestamp
