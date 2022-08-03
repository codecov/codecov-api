from rest_framework import serializers

from core.models import Repository

from ..owner.serializers import OwnerSerializer


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
