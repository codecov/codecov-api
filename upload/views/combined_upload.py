import logging

from django.conf import settings
from django.http import HttpRequest
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from services.archive import ArchiveService

from codecov_auth.authentication.repo_auth import (
    GitHubOIDCTokenAuthentication,
    GlobalTokenAuthentication,
    OrgLevelTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
    TokenlessAuthentication,
    UploadTokenRequiredAuthenticationCheck,
    repo_auth_custom_exception_handler,
)
from upload.serializers import (
    CommitReportSerializer,
    CommitSerializer,
    UploadSerializer,
)
from upload.throttles import UploadsPerCommitThrottle, UploadsPerWindowThrottle
from upload.views.base import GetterMixin
from upload.views.commits import CommitLogicMixin
from upload.views.reports import ReportLogicMixin
from upload.views.uploads import CanDoCoverageUploadsPermission, UploadLogicMixin

log = logging.getLogger(__name__)


class CombinedUploadView(APIView, GetterMixin, CommitLogicMixin, ReportLogicMixin, UploadLogicMixin):
    permission_classes = [CanDoCoverageUploadsPermission]
    authentication_classes = [
        UploadTokenRequiredAuthenticationCheck,
        GlobalTokenAuthentication,
        OrgLevelTokenAuthentication,
        GitHubOIDCTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
        TokenlessAuthentication,
    ]

    def get_exception_handler(self):
        return repo_auth_custom_exception_handler

    def post(self, request: HttpRequest, *args, **kwargs) -> Response:
        # Create commit
        create_commit_data = dict(
            commitid=request.data.get("commit_sha"),
            parent_commit_id=request.data.get("parent_sha"),
            pullid=request.data.get("pull_request_number"),
            branch=request.data.get("branch"),
        )
        commit_serializer = CommitSerializer(data=create_commit_data)
        if not commit_serializer.is_valid():
            return Response(
                commit_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )
        log.info(f"Creating commit for {commit_serializer.validated_data}")
        repository = self.get_repo()
        commit = self.create_commit(commit_serializer, repository)

        # Create report
        commit_report_data = dict(
            code=request.data.get("code"),
        )
        commit_report_serializer = CommitReportSerializer(data=commit_report_data)
        if not commit_report_serializer.is_valid():
            return Response(
                commit_report_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )
        report = self.create_report(commit_report_serializer, repository, commit)

        # Do upload
        upload_data = dict(
            ci_url=request.data.get("build_url"),
            env=request.data.get("env_vars"),
            flags=request.data.get("flags"),
            ci_service=request.data.get("ci_service"),
            job_code=request.data.get("job_code"),
            name=request.data.get("name"),
        )
        upload_serializer = UploadSerializer(data=upload_data)
        if not upload_serializer.is_valid():
            return Response(upload_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        instance = self.create_upload(upload_serializer, repository, commit, report)
        
        repository = instance.report.commit.repository
        commit = instance.report.commit
        
        url = f"{settings.CODECOV_DASHBOARD_URL}/{repository.author.service}/{repository.author.username}/{repository.name}/commit/{commit.commitid}"
        
        archive_service = ArchiveService(repository)
        raw_upload_location = archive_service.create_presigned_put(instance.storage_path)
        
        if instance:
            return Response({"raw_upload_location": raw_upload_location, "url": url}, status=status.HTTP_201_CREATED)
        else:
            return Response(
                upload_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )
