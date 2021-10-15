from rest_framework import serializers

from profiling.models import ProfilingCommit, ProfilingUpload
from services.archive import ArchiveService


class CreatableProfilingCommitRelatedField(serializers.SlugRelatedField):
    def get_queryset(self):
        return ProfilingCommit.objects.filter(
            repository__in=self.context["request"].auth.get_repositories()
        )


class ProfilingUploadSerializer(serializers.ModelSerializer):
    raw_upload_location = serializers.SerializerMethodField()
    profiling = CreatableProfilingCommitRelatedField(
        slug_field="external_id", source="profiling_commit"
    )

    class Meta:
        fields = ("raw_upload_location", "profiling", "created_at", "external_id")
        read_only_fields = ("created_at", "raw_upload_location", "external_id")
        model = ProfilingUpload

    def get_raw_upload_location(self, obj):
        repo = obj.profiling_commit.repository
        archive_service = ArchiveService(repo)
        return archive_service.create_presigned_put(obj.raw_upload_location)


class ProfilingCommitSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfilingCommit
        fields = (
            "created_at",
            "external_id",
            "environment",
            "version_identifier",
        )
        read_only_fields = ("created_at", "external_id")
