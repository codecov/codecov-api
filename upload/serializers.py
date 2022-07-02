from rest_framework import serializers

from codecov_auth.models import Owner
from core.models import Commit
from reports.models import ReportSession
from services.archive import ArchiveService


class UploadSerializer(serializers.ModelSerializer):
    class Meta:
        fields = (
            "download_url",
            "ci_url",
            "external_id",
            "created_at",
            "state",
            "upload_type",
            "flags",
            "env",
            "name",
            "provider",
            "report",
            "storage_path",
            "raw_upload_location",
        )
        read_only_fields = (
            "download_url",
            "ci_url",
            "external_id",
            "created_at",
            "external_id",
            "storage_path",
            "report",
            "raw_upload_location",
        )
        model = ReportSession

    raw_upload_location = serializers.SerializerMethodField()

    def get_raw_upload_location(self, obj: ReportSession):
        repo = obj.report.commit.repository
        archive_service = ArchiveService(repo)
        return archive_service.create_presigned_put(obj.storage_path)


# We don't need this right now but likely will in the future
class MutationTestUploadSerializer(UploadSerializer):
    pass


class OwnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Owner
        fields = (
            "avatar_url",
            "service",
            "username",
            "name",
            "ownerid",
            "integration_id",
        )
        read_only_fields = fields


class CommitSerializer(serializers.ModelSerializer):
    author = OwnerSerializer()

    class Meta:
        model = Commit
        read_only_fields = (
            "message",
            "author",
            "timestamp",
            "ci_passed",
            "state",
        )
        fields = read_only_fields + (
            "commitid",
            "parent_commit_id",
            "pullid",
            "branch",
        )
