import logging

from django.http import HttpRequest, HttpResponseNotAllowed, HttpResponseNotFound
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny

log = logging.getLogger(__name__)


class UploadViews(ListCreateAPIView):
    permission_classes = [
        # TODO: Implement the correct permissions
        AllowAny,
    ]

    def create(self, request: HttpRequest, repo: str, commit_sha: str, reportid: str):
        log.info(
            "Request to create new upload",
            extra=dict(repo=repo, commit_id=commit_sha, reportid=reportid),
        )
        return HttpResponseNotFound("Not available")

    def list(self, request: HttpRequest, repo: str, commit_sha: str, reportid: str):
        return HttpResponseNotAllowed(permitted_methods=["POST"])
