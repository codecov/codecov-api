import logging

from django.http import HttpRequest, HttpResponseNotAllowed
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny, BasePermission
from shared.metrics import metrics

from codecov_auth.authentication.repo_auth import (
    GlobalTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
)
from core.models import Commit, Repository
from reports.models import CommitReport
from services.archive import ArchiveService, MinioEndpoints
from services.redis_configuration import get_redis_connection
from upload.helpers import dispatch_upload_task
from upload.serializers import UploadSerializer
from upload.throttles import UploadsPerCommitThrottle, UploadsPerWindowThrottle

log = logging.getLogger(__name__)


class CanDoCoverageUploadsPermission(BasePermission):
    def has_permission(self, request, view):
        return request.auth is not None and "upload" in request.auth.get_scopes()


class UploadViews(ListCreateAPIView):
    serializer_class = UploadSerializer
    permission_classes = [
        CanDoCoverageUploadsPermission,
    ]
    authentication_classes = [
        GlobalTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
    ]
    throttle_classes = [UploadsPerCommitThrottle, UploadsPerWindowThrottle]

    def perform_create(self, serializer):
        repository = self.get_repo()
        commit = self.get_commit(repository)
        report = self.get_report(commit)
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
        self.trigger_upload_task(repository, commit.commitid, instance)
        metrics.incr("uploads.accepted", 1)
        self.activate_repo(repository)
        return instance

    def list(self, request: HttpRequest, repo: str, commit_sha: str, reportid: str):
        return HttpResponseNotAllowed(permitted_methods=["POST"])

    def trigger_upload_task(self, repository, commit_sha, upload):
        redis = get_redis_connection()
        task_arguments = {"commit": commit_sha, "upload_pk": upload.id, "version": "v4"}
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
        # TODO this is not final - how is getting the repo is still in discuss
        repoid = self.kwargs["repo"]
        try:
            repository = Repository.objects.get(name=repoid)
            return repository
        except Repository.DoesNotExist:
            metrics.incr("uploads.rejected", 1)
            raise ValidationError(f"Repository not found")

    def get_commit(self, repo: Repository) -> Commit:
        commit_sha = self.kwargs["commit_sha"]
        try:
            commit = Commit.objects.get(
                commitid=commit_sha, repository__repoid=repo.repoid
            )
            return commit
        except Commit.DoesNotExist:
            metrics.incr("uploads.rejected", 1)
            raise ValidationError("Commit SHA not found")

    def get_report(self, commit: Commit) -> CommitReport:
        report_id = self.kwargs["reportid"]
        try:
            report = CommitReport.objects.get(
                external_id__exact=report_id, commit__commitid=commit.commitid
            )
            return report
        except CommitReport.DoesNotExist:
            metrics.incr("uploads.rejected", 1)
            raise ValidationError(f"Report not found")
