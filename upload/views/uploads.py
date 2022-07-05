import logging

from django.http import HttpRequest, HttpResponseNotAllowed, HttpResponseNotFound
from django.utils import timezone
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny, BasePermission

from codecov_auth.authentication.repo_auth import (
    GlobalTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
)
from core.models import Commit, Repository
from services.archive import ArchiveService, MinioEndpoints
from services.redis_configuration import get_redis_connection
from upload.helpers import dispatch_upload_task
from upload.serializers import UploadSerializer
from upload.throttles import UploadsPerCommitThrottle, UploadsPerWindowThrottle

log = logging.getLogger(__name__)


class CanDoCoverageUploadsPermission(BasePermission):
    def has_permission(self, request, view):
        return request.auth is not None and "upload" in request.auth.get_scopes()


class UploadViews(ListCreateAPIView):
    serializer_class = UploadSerializer
    authentication_classes = [
        GlobalTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
    ]
    permission_classes = [
        AllowAny,
    ]
    throttle_classes = [UploadsPerCommitThrottle, UploadsPerWindowThrottle]

    def perform_create(self, serializer):
        repoid = self.kwargs["repo"]
        commitid = self.kwargs["commitid"]
        commit: Commit = Commit.objects.get(commitid=commitid)
        repository: Repository = Repository.objects.get(name=repoid)
        archive_service = ArchiveService(repository)
        path = MinioEndpoints.raw.get_path(
            version="v4",
            date=timezone.now().strftime("%Y-%m-%d"),
            repo_hash=archive_service.storage_hash,
            commit_sha=commit.commitid,
            reportid=self.kwargs["reportid"],
        )
        instance = serializer.save(storage_path=path, report_id=self.kwargs["reportid"])
        self.trigger_upload_task(repository, commitid, instance)
        self.activate_repo(repository)
        return instance

    def list(self, request: HttpRequest, repo: str, commitid: str, reportid: str):
        return HttpResponseNotAllowed(permitted_methods=["POST"])

    def trigger_upload_task(self, repository, commit_id, upload):
        redis = get_redis_connection()
        task_arguments = {"commit": commit_id, "upload_pk": upload.id, "version": "v4"}
        dispatch_upload_task(task_arguments, repository, redis)

    def activate_repo(self, repository):
        repository.activated = True
        repository.active = True
        repository.deleted = False
        repository.save(update_fields=["activated", "active", "deleted", "updatestamp"])
