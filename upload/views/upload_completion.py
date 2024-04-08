from loguru import logger

from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response

from codecov_auth.authentication.repo_auth import (
    GitHubOIDCTokenAuthentication,
    GlobalTokenAuthentication,
    OrgLevelTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
)
from reports.models import ReportSession
from services.task import TaskService
from upload.views.base import GetterMixin
from upload.views.uploads import CanDoCoverageUploadsPermission


class UploadCompletionView(CreateAPIView, GetterMixin):
    permission_classes = [CanDoCoverageUploadsPermission]
    authentication_classes = [
        GlobalTokenAuthentication,
        OrgLevelTokenAuthentication,
        GitHubOIDCTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
    ]

    def post(self, request, *args, **kwargs):
        repo = self.get_repo()
        commit = self.get_commit(repo)
        uploads_queryset = ReportSession.objects.filter(
            report__commit=commit,
            report__code=None,
        )
        uploads_count = uploads_queryset.count()
        if not uploads_queryset or uploads_count == 0:
            logger.info(
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
