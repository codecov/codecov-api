import logging

from django.http import HttpRequest, HttpResponseNotAllowed, HttpResponseNotFound
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny

log = logging.getLogger(__name__)


class CommitViews(ListCreateAPIView):
    permission_classes = [
        # TODO: implement the correct permissions
        AllowAny,
    ]

    def create(self, request: HttpRequest, repo: str):
        log.info("Request to create new commit", extra=dict(repo=repo))
        return HttpResponseNotFound("Not available")

    def list(self, request: HttpRequest, repo: str):
        return HttpResponseNotAllowed(permitted_methods=["POST"])
