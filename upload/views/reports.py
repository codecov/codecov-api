import logging
import re

from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseNotAllowed,
    HttpResponseNotFound,
)
from rest_framework import status
from rest_framework.generics import CreateAPIView, ListCreateAPIView
from rest_framework.permissions import AllowAny

from upload.serializers import CommitReportSerializer

log = logging.getLogger(__name__)


class ReportViews(ListCreateAPIView):
    serializer_class = CommitReportSerializer
    permission_classes = [
        # TODO: Implement the correct permissions
        AllowAny,
    ]

    def create(self, request: HttpRequest, repo: str, commit_sha: str):
        log.info(
            "Request to create new report", extra=dict(repo=repo, commit_id=commit_sha)
        )
        return HttpResponseNotFound("Not available")

    def list(self, request: HttpRequest, repo: str, commit_sha: str):
        return HttpResponseNotAllowed(permitted_methods=["POST"])


class ReportResultsView(CreateAPIView):
    # TODO add correct permission classes
    permission_classes = [AllowAny]

    def create(
        self,
        request: HttpRequest,
        service: str,
        repo: str,
        commit_sha: str,
        report_code: str,
    ):
        return HttpResponse(
            status=status.HTTP_200_OK,
        )
