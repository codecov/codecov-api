import logging

from django.http import HttpRequest, HttpResponseNotAllowed
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import BasePermission
from shared.metrics import metrics

from codecov_auth.authentication.repo_auth import (
    GlobalTokenAuthentication,
    OrgLevelTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
)
from core.models import Commit, Repository
from reports.models import CommitReport
from services.archive import ArchiveService, MinioEndpoints
from services.redis_configuration import get_redis_connection
from upload.helpers import dispatch_upload_task
from upload.serializers import UploadSerializer
from upload.throttles import UploadsPerCommitThrottle, UploadsPerWindowThrottle
from upload.views.base import GetterMixin

log = logging.getLogger(__name__)


class CanDoCoverageUploadsPermission(BasePermission):
    def has_permission(self, request, view):
        repository = view.get_repo()
        return (
            request.auth is not None
            and "upload" in request.auth.get_scopes()
            and request.auth.allows_repo(repository)
        )


class UploadViews(ListCreateAPIView, GetterMixin):
    serializer_class = UploadSerializer
    permission_classes = [
        CanDoCoverageUploadsPermission,
    ]
    authentication_classes = [
        GlobalTokenAuthentication,
        OrgLevelTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
    ]
    throttle_classes = [UploadsPerCommitThrottle, UploadsPerWindowThrottle]

    def perform_create(self, serializer):
        repository = self.get_repo()
        commit = self.get_commit(repository)
        report = self.get_report(commit)
        log.info(
            "Request to create new upload",
            extra=dict(repo=repository.name, commit_id=commit.commitid),
        )
        archive_service = ArchiveService(repository)
        path = MinioEndpoints.raw.get_path(
            version="v4",
            date=timezone.now().strftime("%Y-%m-%d"),
            repo_hash=archive_service.storage_hash,
            commit_sha=commit.commitid,
            reportid=report.external_id,
        )
        instance = serializer.save(
            storage_path=path,
            report_id=report.id,
            upload_extras={"format_version": "v1"},
        )
        self.trigger_upload_task(repository, commit.commitid, instance, report)
        metrics.incr("uploads.accepted", 1)
        self.activate_repo(repository)
        return instance

    def list(
        self,
        request: HttpRequest,
        service: str,
        repo: str,
        commit_sha: str,
        report_code: str,
    ):
        return HttpResponseNotAllowed(permitted_methods=["POST"])

    def trigger_upload_task(self, repository, commit_sha, upload, report):
        log.info(
            "Triggering upload task",
            extra=dict(
                repo=repository.name,
                commit_id=commit_sha,
                upload_id=upload.id,
                report_code=report.code,
            ),
        )
        redis = get_redis_connection()
        task_arguments = {
            "commit": commit_sha,
            "upload_id": upload.id,
            "version": "v4",
            "report_code": report.code,
            "reportid": str(report.external_id),
        }
        dispatch_upload_task(task_arguments, repository, redis)

    def activate_repo(self, repository):
        # Only update the fields if needed
        if repository.activated and repository.active and not repository.deleted:
            return
        repository.activated = True
        repository.active = True
        repository.deleted = False
        repository.save(update_fields=["activated", "active", "deleted", "updatestamp"])

    def get_repo(self) -> Repository:
        try:
            repo = super().get_repo()
            return repo
        except ValidationError as exception:
            metrics.incr("uploads.rejected", 1)
            raise exception

    def get_commit(self, repo: Repository) -> Commit:
        try:
            commit = super().get_commit(repo)
            return commit
        except ValidationError as excpetion:
            metrics.incr("uploads.rejected", 1)
            raise excpetion

    def get_report(self, commit: Commit) -> CommitReport:
        try:
            report = super().get_report(commit)
            return report
        except ValidationError as exception:
            metrics.incr("uploads.rejected", 1)
            raise exception
