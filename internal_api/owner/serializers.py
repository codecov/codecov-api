from rest_framework import serializers

from codecov_auth.models import Owner
from codecov_auth.constants import USER_PLANS

from services.billing import BillingService


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


# TODO: needs to account for enterprise/legacy plans
class PlanSerializer(serializers.Serializer):
    name = serializers.SerializerMethodField()
    base_unit_price = serializers.SerializerMethodField()
    billing_rate = serializers.SerializerMethodField()

    def get_name(self, plan):
        if 'free' in plan:
            return "Basic"
        return "Pro Team"

    def get_base_unit_price(self, plan):
        if 'free' in plan:
            return 0
        if 'y' in plan:
            return 10
        return 12

    def get_billing_rate(self, plan):
        if 'free' in plan:
            return None
        if "y" in plan:
            return "annually"
        return "monthly"


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
    plan = serializers.SerializerMethodField()
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

    def get_plan(self, owner):
        if owner.plan in USER_PLANS:
            return PlanSerializer(owner.plan).data
        # TODO: legacy plans

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


class UserSerializer(serializers.ModelSerializer):
    activated = serializers.BooleanField()

    class Meta:
        model = Owner
        fields = (
            'activated',
            'username',
            'email',
            'ownerid',
            'student',
            'name'
        )
