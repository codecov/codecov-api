from rest_framework import serializers

from core.models import Pull
from internal_api.commit.serializers import CommitTotalsSerializer
from internal_api.owner.serializers import OwnerSerializer


class PullSerializer(serializers.ModelSerializer):
    most_recent_commiter = serializers.CharField()
    base_totals = CommitTotalsSerializer()
    head_totals = CommitTotalsSerializer()
    ci_passed = serializers.BooleanField()

    class Meta:
        model = Pull
        fields = (
            "pullid",
            "title",
            "most_recent_commiter",
            "base_totals",
            "head_totals",
            "updatestamp",
            "state",
            "ci_passed",
        )


class PullDetailSerializer(PullSerializer):
    author = OwnerSerializer()

    class Meta:
        model = Pull
        fields = PullSerializer.Meta.fields + ("author",)
