import logging

from django.conf import settings
from django.http import HttpRequest
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from shared.api_archive.archive import ArchiveService
from shared.metrics import inc_counter

from codecov_auth.authentication.repo_auth import (
    GitHubOIDCTokenAuthentication,
    GlobalTokenAuthentication,
    OrgLevelTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
    TokenlessAuthentication,
    UploadTokenRequiredAuthenticationCheck,
    repo_auth_custom_exception_handler,
)
from upload.helpers import generate_upload_prometheus_metrics_labels
from upload.metrics import API_UPLOAD_COUNTER
from upload.serializers import (
    CommitReportSerializer,
    CommitSerializer,
    UploadSerializer,
)
from upload.throttles import UploadsPerCommitThrottle, UploadsPerWindowThrottle
from upload.views.base import GetterMixin
from upload.views.commits import create_commit
from upload.views.reports import create_report
from upload.views.uploads import (
    CanDoCoverageUploadsPermission,
    create_upload,
    get_token_for_analytics,
)

log = logging.getLogger(__name__)


class UploadCoverageView(APIView, GetterMixin):
    permission_classes = [CanDoCoverageUploadsPermission]
    authentication_classes = [
        UploadTokenRequiredAuthenticationCheck,
        GlobalTokenAuthentication,
        OrgLevelTokenAuthentication,
        GitHubOIDCTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
        TokenlessAuthentication,
    ]
    throttle_classes = [UploadsPerCommitThrottle, UploadsPerWindowThrottle]

    def get_exception_handler(self):
        return repo_auth_custom_exception_handler

    def emit_metrics(self, position: str) -> None:
        inc_counter(
            API_UPLOAD_COUNTER,
            labels=generate_upload_prometheus_metrics_labels(
                action="coverage",
                endpoint="upload_coverage",
                request=self.request,
                is_shelter_request=self.is_shelter_request(),
                position=position,
            ),
        )

    def post(self, request: HttpRequest, *args, **kwargs) -> Response:
        self.emit_metrics(position="start")

        # Create commit
        create_commit_data = dict(
            branch=request.data.get("branch"),
            commitid=request.data.get("commitid"),
            parent_commit_id=request.data.get("parent_commit_id"),
            pullid=request.data.get("pullid"),
        )
        commit_serializer = CommitSerializer(data=create_commit_data)
        if not commit_serializer.is_valid():
            return Response(
                commit_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

        repository = self.get_repo()
        self.emit_metrics(position="create_commit")
        commit = create_commit(commit_serializer, repository)

        log.info(
            "Request to create new coverage upload",
            extra=dict(
                repo=repository.name,
                commit=commit.commitid,
            ),
        )

        # Create report
        commit_report_data = dict(
            code=request.data.get("code"),
        )
        commit_report_serializer = CommitReportSerializer(data=commit_report_data)
        if not commit_report_serializer.is_valid():
            return Response(
                commit_report_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

        self.emit_metrics(position="create_report")
        report = create_report(commit_report_serializer, repository, commit)

        # Do upload
        upload_data = dict(
            ci_service=request.data.get("ci_service"),
            ci_url=request.data.get("ci_url"),
            env=request.data.get("env"),
            flags=request.data.get("flags"),
            job_code=request.data.get("job_code"),
            name=request.data.get("name"),
            version=request.data.get("version"),
        )

        if self.is_shelter_request():
            upload_data["storage_path"] = request.data.get("storage_path")

        upload_serializer = UploadSerializer(data=upload_data)
        if not upload_serializer.is_valid():
            return Response(
                upload_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

        self.emit_metrics(position="create_upload")
        upload = create_upload(
            upload_serializer,
            repository,
            commit,
            report,
            self.is_shelter_request(),
            get_token_for_analytics(commit, self.request),
        )

        self.emit_metrics(position="end")

        if not upload:
            return Response(
                upload_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

        commitid = upload.report.commit.commitid
        upload_repository = upload.report.commit.repository
        url = f"{settings.CODECOV_DASHBOARD_URL}/{upload_repository.author.service}/{upload_repository.author.username}/{upload_repository.name}/commit/{commitid}"
        archive_service = ArchiveService(upload_repository)
        raw_upload_location = archive_service.create_presigned_put(upload.storage_path)
        return Response(
            {
                "external_id": str(upload.external_id),
                "created_at": upload.created_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "raw_upload_location": raw_upload_location,
                "url": url,
            },
            status=status.HTTP_201_CREATED,
        )
