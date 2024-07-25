from rest_framework import serializers
from shared.django_apps.codecov_auth.models import (
    Account,
    InvoiceBilling,
    StripeBilling,
)

from api.internal.owner.serializers import PlanSerializer


class StripeBillingSerializer(serializers.ModelSerializer):
    class Meta:
        model = StripeBilling
        fields = ("customer_id", "subscription_id", "is_active")


class InvoiceBillingSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceBilling
        fields = ("account_manager", "is_active")


class BaseAccountSerializer(serializers.ModelSerializer):
    stripe_billing = StripeBillingSerializer(many=True, read_only=True)
    invoice_billing = InvoiceBillingSerializer(many=True, read_only=True)
    plan = PlanSerializer(source="pretty_plan")

    class Meta:
        model = Account
        read_only_fields = (
            "name",
            "is_delinquent",
            "free_seat_count",
            "plan_seat_count",
            "total_seat_count",  # == plan_seat_count + free_seat_count
            "activated_user_count",
            "activated_student_count",
            "all_user_count",  # == activated_user_count + activated_student_count
            "organizations_count",
            "available_seat_count",  # == total_seat_count - activated_user_count
            "plan",
            "plan_auto_activate",
            "stripe_billing",
            "invoice_billing",
        )
        # right now it's a read-only experience
        fields = read_only_fields
