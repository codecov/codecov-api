from rest_framework import serializers

from api.public.v2.owner.serializers import OwnerSerializer
from api.shared.commit.serializers import CommitTotalsSerializer
from core.models import Pull


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
