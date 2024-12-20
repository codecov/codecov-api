from rest_framework import serializers

from codecov_auth.models import Owner


class OwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Owner
        fields = (
            "service",
            "username",
            "name",
        )
        read_only_fields = fields


class UserSerializer(OwnerSerializer):
    activated = serializers.BooleanField()
    is_admin = serializers.BooleanField()

    class Meta:
        model = Owner
        fields = OwnerSerializer.Meta.fields + ("activated", "is_admin", "email")


class UserSessionSerializer(serializers.ModelSerializer):
    has_active_session = serializers.BooleanField()
    expiry_date = serializers.DateTimeField()

    class Meta:
        model = Owner
        fields = ("username", "name", "has_active_session", "expiry_date")
        read_only_fields = fields


class UserUpdateActivationSerializer(serializers.ModelSerializer):
    activated = serializers.BooleanField()

    class Meta:
        model = Owner
        fields = ("activated",)
