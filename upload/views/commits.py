import logging

from django.http import HttpRequest, HttpResponseNotAllowed, HttpResponseNotFound
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny

from core.models import Commit

log = logging.getLogger(__name__)


class CommitViews(ListCreateAPIView):
    queryset = Commit.objects.all()
    permission_classes = [
        AllowAny,
    ]

    def create(self, request: HttpRequest, repo: str):
        log.info("Received request to create Commit", extra=dict(repo=repo))
        return HttpResponseNotFound("Not available")

    def list(self, request: HttpRequest, repo: str):
        return HttpResponseNotAllowed(permitted_methods=["POST"])
