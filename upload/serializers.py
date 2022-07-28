from rest_framework import serializers

from reports.models import ReportSession
from services.archive import ArchiveService


class UploadSerializer(serializers.ModelSerializer):
    class Meta:
        fields = (
            "ci_url",
            "external_id",
            "created_at",
            "state",
            "upload_type",
            "flags",
            "env",
            "name",
            "provider",
            "storage_path",
            "raw_upload_location",
        )
        read_only_fields = (
            "ci_url",
            "external_id",
            "created_at",
            "external_id",
            "storage_path",
            "raw_upload_location",
        )
        model = ReportSession

    raw_upload_location = serializers.SerializerMethodField()

    def get_raw_upload_location(self, obj: ReportSession):
        repo = obj.report.commit.repository
        archive_service = ArchiveService(repo)
        return archive_service.create_presigned_put(obj.storage_path)
