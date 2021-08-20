from rest_framework import serializers

from core.models import Pull


class PullSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pull
        read_only_fields = (
            "pullid",
            "title",
            "base",
            "head",
            "compared_to",
            "updatestamp",
            "state",
        )
        fields = read_only_fields + ("user_provided_base_sha",)
