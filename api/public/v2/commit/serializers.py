from rest_framework import serializers

from api.public.v2.owner.serializers import OwnerSerializer
from api.shared.commit.serializers import (
    CommitTotalsSerializer,
    ReportSerializer,
    UploadTotalsSerializer,
)
from api.shared.serializers import StringListField
from core.models import Commit
from reports.models import ReportSession


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
    parent = serializers.CharField(
        label="commit SHA of first ancestor commit with coverage",
        source="parent_commit_id",
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
            "parent",
        )


class CommitDetailSerializer(CommitSerializer):
    report = ReportSerializer(source="full_report", label="coverage report")

    class Meta:
        model = Commit
        fields = CommitSerializer.Meta.fields + ("report",)


class CommitUploadsSerializer(serializers.ModelSerializer):
    created_at = serializers.CharField()
    updated_at = serializers.CharField()
    storage_path = serializers.CharField()
    flags = StringListField(source="flag_names")
    provider = serializers.CharField()
    build_code = serializers.CharField()
    name = serializers.CharField()
    job_code = serializers.CharField()
    build_url = serializers.CharField()
    state = serializers.CharField()
    env = serializers.JSONField()
    upload_type = serializers.CharField()
    upload_extras = serializers.JSONField()
    totals = UploadTotalsSerializer(source="uploadleveltotals")

    class Meta:
        model = ReportSession
        fields = (
            "created_at",
            "updated_at",
            "storage_path",
            "flags",
            "provider",
            "build_code",
            "name",
            "job_code",
            "build_url",
            "state",
            "env",
            "upload_type",
            "upload_extras",
            "totals",
        )
