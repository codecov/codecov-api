from rest_framework import serializers

from api.public.v2.owner.serializers import OwnerSerializer
from core.models import Repository


class RepoSerializer(serializers.ModelSerializer):
    author = OwnerSerializer()

    class Meta:
        model = Repository
        read_only_fields = (
            "repoid",
            "name",
            "private",
            "updatestamp",
            "author",
            "language",
        )
        fields = read_only_fields + ("branch", "active", "activated")
