import logging
from distutils.log import info

from django.http import HttpRequest, HttpResponseNotAllowed, HttpResponseNotFound
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny

log = logging.getLogger(__name__)


class UploadViews(ListCreateAPIView):
    permission_classes = [
        AllowAny,
    ]

    def create(self, request: HttpRequest, repo: str, commit_id: str, report_id: str):
        log.info(
            "Request to create new upload",
            extra=dict(repo=repo, commit_id=commit_id, report_id=report_id),
        )
        return HttpResponseNotFound(f"Not available")

    def list(self, request: HttpRequest, repo: str, commit_id: str, report_id: str):
        return HttpResponseNotAllowed(permitted_methods=["POST"])
