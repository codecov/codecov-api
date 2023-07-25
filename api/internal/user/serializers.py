from rest_framework import serializers

from api.internal.owner.serializers import OwnerSerializer
from codecov_auth.models import User


class UserSerializer(serializers.ModelSerializer):
    owners = OwnerSerializer(many=True)

    class Meta:
        model = User
        fields = (
            "email",
            "name",
            "external_id",
            "owners",
        )

        read_only_fields = fields
