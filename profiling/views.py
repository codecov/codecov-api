import logging
from uuid import uuid4

from rest_framework import serializers
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import BasePermission
from profiling.models import ProfilingUpload, ProfilingCommit
from services.archive import ArchiveService, MinioEndpoints
from services.task import TaskService
from codecov_auth.authentication.repo_auth import RepositoryTokenAuthentication

log = logging.getLogger(__name__)


class CreatableProfilingCommitRelatedField(serializers.Field):
    def to_internal_value(self, data):
        repo = self.context["request"].auth.get_repositories()[0]
        try:
            obj, was_created = ProfilingCommit.objects.get_or_create(
                repository=repo,
                version_identifier=data,
                defaults=dict(
                    last_joined_uploads_at=None,
                    last_summarized_at=None,
                    joined_location=None,
                    summarized_location=None,
                ),
            )
            return obj
        except (TypeError, ValueError):
            self.fail("invalid")

    def to_representation(self, obj):
        return obj.version_identifier


class ProfilingUploadSerializer(serializers.ModelSerializer):
    raw_upload_location = serializers.SerializerMethodField()
    profiling = CreatableProfilingCommitRelatedField(source="profiling_commit")

    class Meta:
        fields = ("raw_upload_location", "profiling", "created_at", "external_id")
        read_only_fields = ("created_at", "raw_upload_location", "external_id")
        model = ProfilingUpload

    def get_raw_upload_location(self, obj):
        repo = obj.profiling_commit.repository
        archive_service = ArchiveService(repo)
        return archive_service.create_presigned_put(obj.raw_upload_location)


class CanDoProfilingUploadsPermission(BasePermission):
    def has_permission(self, request, view):
        return "profiling" in request.auth.get_scopes()


class ProfilingUploadCreateView(CreateAPIView):
    serializer_class = ProfilingUploadSerializer
    authentication_classes = [RepositoryTokenAuthentication]
    permission_classes = [CanDoProfilingUploadsPermission]

    def perform_create(self, serializer):
        location = "{}.txt".format(uuid4())
        archive_service = ArchiveService(self.request.auth.get_repositories()[0])
        path = MinioEndpoints.profiling_upload.get_path(
            version="v4",
            repo_hash=archive_service.storage_hash,
            profiling_version=serializer.validated_data[
                "profiling_commit"
            ].version_identifier,
            location=location,
        )
        instance = serializer.save(raw_upload_location=path)
        task = TaskService().normalize_profiling_upload(instance.id)
        log.info("Spun normalization task", extra=dict(task_id=task.id))
        return instance
