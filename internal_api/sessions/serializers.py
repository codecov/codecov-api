from rest_framework import serializers
from codecov_auth.models import Session
from internal_api.owner.serializers import OwnerSerializer


import logging

log = logging.getLogger(__name__)


class SessionSerializer(serializers.ModelSerializer):
    owner_info = OwnerSerializer(read_only=True, source="owner")

    class Meta:
        model = Session
        fields = (
            "sessionid",
            "ip",
            "lastseen",
            "useragent",
            "owner_info",
            "owner",
            "type",
            "name",
        )


class SessionWithTokenSerializer(SessionSerializer):
    name = serializers.CharField(required=True)
    type = serializers.CharField(required=True)

    class Meta:
        model = Session
        fields = ("token",) + SessionSerializer.Meta.fields

    def validate_type(self, type_val):
        if type_val != Session.SessionType.API:
            raise serializers.ValidationError(
                f"You can only create sessions of type '{Session.SessionType.API}'"
            )
        return type_val

    def create(self, validated_data):
        return Session.objects.create(
            name=validated_data["name"],
            owner=validated_data["owner"],
            type=validated_data["type"],
        )
