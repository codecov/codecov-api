import logging
from uuid import uuid4

from rest_framework.generics import CreateAPIView
from rest_framework.permissions import BasePermission

from codecov_auth.authentication.repo_auth import RepositoryTokenAuthentication
from profiling.models import ProfilingCommit
from profiling.serializers import ProfilingCommitSerializer, ProfilingUploadSerializer
from services.archive import ArchiveService, MinioEndpoints
from services.task import TaskService

log = logging.getLogger(__name__)


class CanDoProfilingUploadsPermission(BasePermission):
    def has_permission(self, request, view):
        return request.auth is not None and "profiling" in request.auth.get_scopes()


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
            ].external_id.hex,
            location=location,
        )
        instance = serializer.save(raw_upload_location=path)
        task = TaskService().normalize_profiling_upload(instance.id)
        log.info("Spun normalization task", extra=dict(task_id=task.id))
        return instance


class ProfilingCommitCreateView(CreateAPIView):
    serializer_class = ProfilingCommitSerializer
    authentication_classes = [RepositoryTokenAuthentication]
    permission_classes = [CanDoProfilingUploadsPermission]

    def perform_create(self, serializer):
        code = serializer.validated_data["code"]
        repository = self.request.auth.get_repositories()[0]
        instance, was_created = ProfilingCommit.objects.get_or_create(
            code=code, repository=repository,
        )
        serializer.instance = instance
        if was_created:
            log.info(
                "Creating new profiling commit", extra=dict(repoid=repository.repoid)
            )
        return serializer.save()
