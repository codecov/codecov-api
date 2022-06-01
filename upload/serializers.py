from rest_framework import serializers

from reports.models import ReportSession
from services.archive import ArchiveService


class UploadSerializer(serializers.ModelSerializer):
    class Meta:
        fields = (
            "download_url",
            "ci_url",
            "build_url",
            "external_id",
            "created_at",
            "external_id",
            "state",
            "upload_type",
            "flags",
            "env",
            "name",
            "provider",
            "report",
        )
        read_only_fields = (
            "download_url",
            "ci_url",
            "build_url",
            "external_id",
            "created_at",
            "external_id",
            "storage_path",
            "report",
        )
        model = ReportSession
