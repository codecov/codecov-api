from rest_framework import serializers

from api.public.v2.owner.serializers import OwnerSerializer
from api.shared.commit.serializers import CommitTotalsSerializer, ReportSerializer
from core.models import Commit


class CommitSerializer(serializers.ModelSerializer):
    commitid = serializers.CharField(label="commit SHA")
    message = serializers.CharField(label="commit message")
    timestamp = serializers.DateTimeField(label="timestamp when commit was made")
    ci_passed = serializers.BooleanField(
        label="indicates whether the CI process passed for this commit"
    )
    author = OwnerSerializer(label="author of the commit")
    branch = serializers.CharField(
        label="branch name on which this commit currently lives"
    )
    totals = CommitTotalsSerializer(label="coverage totals")
    state = serializers.ChoiceField(
        label="Codecov processing state for this commit",
        choices=Commit.CommitStates.choices,
    )

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
    report = ReportSerializer(source="full_report", label="coverage report")

    class Meta:
        model = Commit
        fields = CommitSerializer.Meta.fields + ("report",)
