from rest_framework import serializers

from codecov_auth.models import Owner

class AccountSerializer(serializers.ModelSerializer):
    # TODO: Permissions?
    class Meta:
        model = Owner
        fields = (

        )