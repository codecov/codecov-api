import logging
from typing import Any, Callable

from django.http import HttpRequest
from rest_framework import serializers, status
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from shared.metrics import inc_counter

from codecov_auth.authentication.repo_auth import (
    GitHubOIDCTokenAuthentication,
    GlobalTokenAuthentication,
    OrgLevelTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
    UploadTokenRequiredAuthenticationCheck,
    repo_auth_custom_exception_handler,
)
from services.task import TaskService
from upload.helpers import generate_upload_prometheus_metrics_labels
from upload.metrics import API_UPLOAD_COUNTER
from upload.views.base import GetterMixin
from upload.views.uploads import CanDoCoverageUploadsPermission

log = logging.getLogger(__name__)


class TransplantReportSerializer(serializers.Serializer):
    from_sha = serializers.CharField(required=True)
    to_sha = serializers.CharField(required=True)


class TransplantReportView(CreateAPIView, GetterMixin):
    permission_classes = [CanDoCoverageUploadsPermission]
    authentication_classes = [
        UploadTokenRequiredAuthenticationCheck,
        GlobalTokenAuthentication,
        OrgLevelTokenAuthentication,
        GitHubOIDCTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
    ]

    def get_exception_handler(self) -> Callable[[Exception, dict[str, Any]], Response]:
        return repo_auth_custom_exception_handler

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
        inc_counter(
            API_UPLOAD_COUNTER,
            labels=generate_upload_prometheus_metrics_labels(
                action="coverage",
                endpoint="transplant_report",
                request=self.request,
                is_shelter_request=self.is_shelter_request(),
            ),
        )
        serializer = TransplantReportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        TaskService().transplant_report(
            repo_id=self.get_repo().repoid,
            from_sha=data["from_sha"],
            to_sha=data["to_sha"],
        )

        return Response(
            data={"result": "All good, transplant scheduled"},
            status=status.HTTP_200_OK,
        )
