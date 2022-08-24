from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

import services.self_hosted as self_hosted
from codecov_auth.models import Owner


class UserSerializer(serializers.ModelSerializer):
    is_admin = serializers.BooleanField()
    activated = serializers.BooleanField()

    class Meta:
        model = Owner
        fields = (
            "ownerid",
            "username",
            "email",
            "name",
            "is_admin",
            "activated",
        )

    def update(self, instance, validated_data):
        if "activated" in validated_data:
            if validated_data["activated"] is True:
                try:
                    self_hosted.activate_owner(instance)
                except self_hosted.LicenseException as err:
                    raise PermissionDenied(err)
            else:
                self_hosted.deactivate_owner(instance)

        # re-query for object to get updated `activated` value
        return self.context["view"].get_queryset().filter(pk=instance.pk).first()
