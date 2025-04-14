import logging
from typing import Any, Callable

from django.http import HttpRequest
from rest_framework import serializers, status
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.authentication import BasicAuthentication, SessionAuthentication

from api.public.v2.repo.permissions import RepositoryOrgMemberPermissions
from api.shared.mixins import RepoPropertyMixin
from api.shared.permissions import RepositoryArtifactPermissions, SuperTokenPermissions, UserIsAdminPermissions
from codecov_auth.authentication import SessionAuthentication, SuperTokenAuthentication, UserTokenAuthentication
from codecov_auth.authentication.repo_auth import (
    GitHubOIDCTokenAuthentication,
    GlobalTokenAuthentication,
    OrgLevelTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
    UploadTokenRequiredAuthenticationCheck,
    repo_auth_custom_exception_handler,
)
from rest_framework.permissions import AllowAny
from services.task import TaskService
from upload.views.uploads import CanDoCoverageUploadsPermission

log = logging.getLogger(__name__)


class TransplantReportSerializer(serializers.Serializer):
    from_sha = serializers.CharField(required=True)
    to_sha = serializers.CharField(required=True)


class TransplantReportView(CreateAPIView, RepoPropertyMixin):
    authentication_classes = [
        SuperTokenAuthentication,
        UserTokenAuthentication,
        BasicAuthentication,
        SessionAuthentication,
    ]
    permission_classes = [RepositoryArtifactPermissions, RepositoryOrgMemberPermissions]

    def get_exception_handler(self) -> Callable[[Exception, dict[str, Any]], Response]:
        return repo_auth_custom_exception_handler

    def create(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Response:
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
