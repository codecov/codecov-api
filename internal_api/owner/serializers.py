import logging
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from codecov_auth.models import Owner
from codecov_auth.constants import USER_PLAN_REPRESENTATIONS

from services.billing import BillingService


log = logging.getLogger(__name__)


class OwnerSerializer(serializers.ModelSerializer):
    stats = serializers.SerializerMethodField()

    class Meta:
        model = Owner
        fields = (
            'avatar_url',
            'service',
            'username',
            'email',
            'stats',
            'ownerid',
            'integration_id'
        )

    def get_stats(self, obj):
        if obj.cache and 'stats' in obj.cache:
            return obj.cache['stats']


class StripeLineItemSerializer(serializers.Serializer):
    description = serializers.CharField()
    amount = serializers.FloatField()
    currency = serializers.CharField()
    period = serializers.JSONField()


class StripeInvoiceSerializer(serializers.Serializer):
    number = serializers.CharField()
    status = serializers.CharField()
    created = serializers.IntegerField()
    period_start = serializers.IntegerField()
    period_end = serializers.IntegerField()
    due_date = serializers.CharField()
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


class AccountDetailsSerializer(serializers.ModelSerializer):
    plan = serializers.JSONField(source="pretty_plan")
    admins = serializers.SerializerMethodField()
    recent_invoices = serializers.SerializerMethodField()

    class Meta:
        model = Owner
        fields = (
            'activated_user_count',
            'inactive_user_count',
            'plan_auto_activate',
            'integration_id',
            'plan',
            'admins',
            'recent_invoices'
        )

    def get_admins(self, owner):
        return OwnerSerializer(
            Owner.objects.filter(ownerid__in=owner.admins),
            many=True
        ).data if owner.admins else []

    def get_recent_invoices(self, owner):
        return StripeInvoiceSerializer(
            BillingService().list_invoices(owner, limit=4),
            many=True
        ).data

    def update(self, instance, validated_data):
        if "pretty_plan" in validated_data:
            plan = validated_data.pop("pretty_plan")
            BillingService().update_plan(instance, plan)
        super().update(instance, validated_data)
        return self.context["view"].get_object()


class UserSerializer(serializers.ModelSerializer):
    activated = serializers.BooleanField()
    is_admin = serializers.BooleanField()

    class Meta:
        model = Owner
        fields = (
            'activated',
            'is_admin',
            'username',
            'email',
            'ownerid',
            'student',
            'name'
        )

    def update(self, instance, validated_data):
        owner = self.context["view"].owner

        if "activated" in validated_data:
            if validated_data["activated"] is True and owner.can_activate_user(instance):
                owner.activate_user(instance)
            elif validated_data["activated"] is False:
                owner.deactivate_user(instance)
            else:
                raise PermissionDenied(f"Cannot activate user {instance.username} -- not enough seats left.")

        if "is_admin" in validated_data:
            if validated_data["is_admin"]:
                owner.add_admin(instance)
            else:
                owner.remove_admin(instance)

        # Re-fetch from DB to set activated and admin fields
        return self.context["view"].get_object()
