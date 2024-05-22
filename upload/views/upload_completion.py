import logging

from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from sentry_sdk import metrics as sentry_metrics

from codecov_auth.authentication.repo_auth import (
    GitHubOIDCTokenAuthentication,
    GlobalTokenAuthentication,
    OrgLevelTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
    repo_auth_custom_exception_handler,
)
from reports.models import ReportSession
from services.task import TaskService
from upload.helpers import generate_upload_sentry_metrics_tags
from upload.views.base import GetterMixin
from upload.views.uploads import CanDoCoverageUploadsPermission

log = logging.getLogger(__name__)


class UploadCompletionView(CreateAPIView, GetterMixin):
    permission_classes = [CanDoCoverageUploadsPermission]
    authentication_classes = [
        GlobalTokenAuthentication,
        OrgLevelTokenAuthentication,
        GitHubOIDCTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
    ]

    def get_exception_handler(self):
        return repo_auth_custom_exception_handler

    def post(self, request, *args, **kwargs):
        repo = self.get_repo()
        commit = self.get_commit(repo)
        uploads_queryset = ReportSession.objects.filter(
            report__commit=commit,
            report__code=None,
        )
        uploads_count = uploads_queryset.count()
        if not uploads_queryset or uploads_count == 0:
            log.info(
                "Cannot trigger notifications as we didn't find any uploads for the provided commit",
                extra=dict(
                    repo=repo.name, commit=commit.commitid, pullid=commit.pullid
                ),
            )
            return Response(
                data={
                    "uploads_total": 0,
                    "uploads_success": 0,
                    "uploads_processing": 0,
                    "uploads_error": 0,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        in_progress_uploads = 0
        errored_uploads = 0
        for upload in uploads_queryset:
            # upload is still processing
            if not upload.state:
                in_progress_uploads += 1
            elif upload.state == "error":
                errored_uploads += 1

        TaskService().manual_upload_completion_trigger(repo.repoid, commit.commitid)
        sentry_metrics.incr(
            "upload",
            tags=generate_upload_sentry_metrics_tags(
                action="coverage",
                endpoint="upload_complete",
                request=self.request,
                repository=repo,
                is_shelter_request=self.is_shelter_request(),
            ),
        )
        return Response(
            data={
                "uploads_total": uploads_count,
                "uploads_success": uploads_count
                - in_progress_uploads
                - errored_uploads,
                "uploads_processing": in_progress_uploads,
                "uploads_error": errored_uploads,
            },
            status=status.HTTP_200_OK,
        )
