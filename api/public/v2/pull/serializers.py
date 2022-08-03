from rest_framework import serializers

from api.shared.commit.serializers import CommitTotalsSerializer
from core.models import Pull

from ..owner.serializers import OwnerSerializer


class PullSerializer(serializers.ModelSerializer):
    base_totals = CommitTotalsSerializer()
    head_totals = CommitTotalsSerializer()
    ci_passed = serializers.BooleanField()
    author = OwnerSerializer()

    class Meta:
        model = Pull
        fields = (
            "pullid",
            "title",
            "base_totals",
            "head_totals",
            "updatestamp",
            "state",
            "ci_passed",
            "author",
        )
