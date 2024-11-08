import logging

from django.conf import settings
from django.http import HttpRequest
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
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
from services.archive import ArchiveService
from upload.helpers import generate_upload_prometheus_metrics_labels
from upload.metrics import API_UPLOAD_COUNTER
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


class CombinedUploadView(
    APIView, GetterMixin, CommitLogicMixin, ReportLogicMixin, UploadLogicMixin
):
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

    def post(self, request: HttpRequest, *args, **kwargs) -> Response:
        inc_counter(
            API_UPLOAD_COUNTER,
            labels=generate_upload_prometheus_metrics_labels(
                action="coverage",
                endpoint="combined_upload",
                request=self.request,
                is_shelter_request=self.is_shelter_request(),
                position="start",
            ),
        )

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

        inc_counter(
            API_UPLOAD_COUNTER,
            labels=generate_upload_prometheus_metrics_labels(
                action="coverage",
                endpoint="combined_upload",
                request=self.request,
                is_shelter_request=self.is_shelter_request(),
                position="create_commit",
            ),
        )
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

        inc_counter(
            API_UPLOAD_COUNTER,
            labels=generate_upload_prometheus_metrics_labels(
                action="coverage",
                endpoint="combined_upload",
                request=self.request,
                is_shelter_request=self.is_shelter_request(),
                position="create_report",
            ),
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
            return Response(
                upload_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )

        inc_counter(
            API_UPLOAD_COUNTER,
            labels=generate_upload_prometheus_metrics_labels(
                action="coverage",
                endpoint="combined_upload",
                request=self.request,
                is_shelter_request=self.is_shelter_request(),
                position="create_upload",
            ),
        )
        upload = self.create_upload(upload_serializer, repository, commit, report)

        inc_counter(
            API_UPLOAD_COUNTER,
            labels=generate_upload_prometheus_metrics_labels(
                action="coverage",
                endpoint="combined_upload",
                request=self.request,
                is_shelter_request=self.is_shelter_request(),
                position="end",
            ),
        )

        if upload:
            commitid = upload.report.commit.commitid
            upload_repository = upload.report.commit.repository
            url = f"{settings.CODECOV_DASHBOARD_URL}/{upload_repository.author.service}/{upload_repository.author.username}/{upload_repository.name}/commit/{commitid}"
            archive_service = ArchiveService(upload_repository)
            raw_upload_location = archive_service.create_presigned_put(
                upload.storage_path
            )
            return Response(
                {
                    "url": url,
                    "raw_upload_location": raw_upload_location,
                },
                status=status.HTTP_201_CREATED,
            )
        else:
            return Response(
                upload_serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )
