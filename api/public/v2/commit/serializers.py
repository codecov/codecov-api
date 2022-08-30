from rest_framework import serializers

from api.public.v2.owner.serializers import OwnerSerializer
from api.shared.commit.serializers import CommitTotalsSerializer, ReportSerializer
from core.models import Commit


class CommitSerializer(serializers.ModelSerializer):
    author = OwnerSerializer()
    totals = CommitTotalsSerializer()

    class Meta:
        model = Commit
        fields = (
            "commitid",
            "message",
            "timestamp",
            "ci_passed",
            "author",
            "branch",
            "totals",
            "state",
        )


class CommitDetailSerializer(CommitSerializer):
    report = ReportSerializer(source="full_report")

    class Meta:
        model = Commit
        fields = CommitSerializer.Meta.fields + ("report",)
