from rest_framework import serializers

from codecov_auth.models import Owner
from core.models import Commit, Repository
from reports.models import CommitReport, ReportResults, ReportSession
from services.archive import ArchiveService


class UploadSerializer(serializers.ModelSerializer):
    class Meta:
        read_only_fields = (
            "external_id",
            "created_at",
            "storage_path",
            "raw_upload_location",
            "state",
            "provider",
        )
        fields = read_only_fields + (
            "ci_url",
            "upload_type",
            "flags",
            "env",
            "name",
        )
        model = ReportSession

    raw_upload_location = serializers.SerializerMethodField()

    def get_raw_upload_location(self, obj: ReportSession):
        repo = obj.report.commit.repository
        archive_service = ArchiveService(repo)
        return archive_service.create_presigned_put(obj.storage_path)


class OwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Owner
        fields = (
            "avatar_url",
            "service",
            "username",
            "name",
            "ownerid",
        )
        read_only_fields = fields


class RepositorySerializer(serializers.ModelSerializer):
    is_private = serializers.BooleanField(source="private")

    class Meta:
        model = Repository
        fields = ("name", "is_private", "active", "language", "yaml")
        read_only_fields = fields


class CommitSerializer(serializers.ModelSerializer):
    author = OwnerSerializer(read_only=True)
    repository = RepositorySerializer(read_only=True)

    class Meta:
        model = Commit
        read_only_fields = (
            "message",
            "timestamp",
            "ci_passed",
            "state",
            "repository",
            "author",
        )
        fields = read_only_fields + (
            "commitid",
            "parent_commit_id",
            "pullid",
            "branch",
        )

    def create(self, validated_data):
        commit = Commit.objects.filter(
            repository=validated_data.get("repository"),
            commitid=validated_data.get("commitid"),
        ).first()
        if commit:
            return commit
        return super().create(validated_data)


class CommitReportSerializer(serializers.ModelSerializer):
    commit_sha = serializers.CharField(source="commit.commitid", read_only=True)

    class Meta:
        model = CommitReport
        read_only_fields = (
            "external_id",
            "created_at",
            "commit_sha",
        )
        fields = read_only_fields + ("code",)


class ReportResultsSerializer(serializers.ModelSerializer):
    report = CommitReportSerializer(read_only=True)

    class Meta:
        model = ReportResults
        read_only_fields = (
            "external_id",
            "report",
            "state",
            "result",
            "completed_at",
        )
        fields = read_only_fields
