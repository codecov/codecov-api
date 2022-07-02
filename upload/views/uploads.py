import logging

from django.http import HttpRequest, HttpResponseNotAllowed, HttpResponseNotFound
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny, BasePermission

from upload.serializers import UploadSerializer
from upload.throttles import UploadsPerCommitThrottle, UploadsPerWindowThrottle

log = logging.getLogger(__name__)


class CanDoCoverageUploadsPermission(BasePermission):
    def has_permission(self, request, view):
        return request.auth is not None and "upload" in request.auth.get_scopes()


class UploadViews(ListCreateAPIView):
    serializer_class = UploadSerializer
    permission_classes = [
        AllowAny,
    ]
    throttle_classes = [UploadsPerCommitThrottle, UploadsPerWindowThrottle]

    def create(self, request: HttpRequest, repo: str, commit_id: str, report_id: str):
        log.info(
            "Request to create new upload",
            extra=dict(repo=repo, commit_id=commit_id, report_id=report_id),
        )
        return HttpResponseNotFound(f"Not available")

    def list(self, request: HttpRequest, repo: str, commit_id: str, report_id: str):
        return HttpResponseNotAllowed(permitted_methods=["POST"])
