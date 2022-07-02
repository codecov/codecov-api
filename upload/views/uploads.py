import logging

from django.http import HttpRequest, HttpResponseNotAllowed, HttpResponseNotFound
from django.utils import timezone
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny, BasePermission

from core.models import Commit, Repository
from services.archive import ArchiveService, MinioEndpoints
from upload.serializers import UploadSerializer
from upload.throttles import UploadsPerCommitThrottle, UploadsPerWindowThrottle

log = logging.getLogger(__name__)


class CanDoCoverageUploadsPermission(BasePermission):
    def has_permission(self, request, view):
        return request.auth is not None and "upload" in request.auth.get_scopes()


class UploadViews(ListCreateAPIView):
    serializer_class = UploadSerializer
    permission_classes = [
        CanDoCoverageUploadsPermission,
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

        return instance

    def list(self, request: HttpRequest, repo: str, commit_id: str, report_id: str):
        return HttpResponseNotAllowed(permitted_methods=["POST"])
