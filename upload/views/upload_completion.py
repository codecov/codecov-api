import logging

from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response

from codecov_auth.authentication.repo_auth import (
    GlobalTokenAuthentication,
    OrgLevelTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
)
from reports.models import ReportSession
from upload.views.base import GetterMixin
from upload.views.uploads import CanDoCoverageUploadsPermission

log = logging.getLogger(__name__)


class UploadCompletionView(CreateAPIView, GetterMixin):
    permission_classes = [CanDoCoverageUploadsPermission]
    authentication_classes = [
        GlobalTokenAuthentication,
        OrgLevelTokenAuthentication,
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
            log.info(
                "Cannot trigger notifications as we didn't find any uploads for the provided commit",
                extra=dict(
                    repo=repo.name, commit=commit.commitid, pullid=commit.pullid
                ),
            )
            return Response(
                data={
                    "result": f"Couldn't find any uploads for your commit {commit.commitid[:7]}",
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

        response_txt = ""
        if in_progress_uploads > 0 and errored_uploads > 0:
            response_txt = f"{errored_uploads} out of {uploads_count} uploads did not get processed successfully, {in_progress_uploads} out of {uploads_count} uploads are still being in process, we'll be sending you notifications once your uploads finish processing and based on the successfully processed ones."
        elif in_progress_uploads > 0:
            response_txt = f"{in_progress_uploads} out of {uploads_count} uploads are still being in process. We'll be sending you notifications once your uploads finish processing."
        elif errored_uploads > 0:
            response_txt = f"{errored_uploads} out of {uploads_count} uploads did not get processed successfully. Sending notifications based on the processed uploads."

        # TODO trigger a task here that does the waiting and triggering the notifications
        return Response(
            data={
                "result": response_txt
                if response_txt
                else "All uploads got processed successfully. Triggering notifications now"
            },
            status=status.HTTP_200_OK,
        )
