import logging

from django.http import HttpRequest, HttpResponseNotAllowed
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import BasePermission
from shared.config import get_config
from shared.metrics import metrics

from codecov_auth.authentication.repo_auth import (
    GlobalTokenAuthentication,
    OrgLevelTokenAuthentication,
    OrgLevelTokenRepositoryAuth,
    RepositoryLegacyTokenAuthentication,
    TokenlessAuth,
    TokenlessAuthentication,
)
from codecov_auth.models import OrganizationLevelToken
from core.models import Commit, Repository
from reports.models import CommitReport, ReportSession
from services.analytics import AnalyticsService
from services.archive import ArchiveService, MinioEndpoints
from services.redis_configuration import get_redis_connection
from upload.helpers import dispatch_upload_task, validate_activated_repo
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
        TokenlessAuthentication,
    ]
    throttle_classes = [UploadsPerCommitThrottle, UploadsPerWindowThrottle]

    def perform_create(self, serializer: UploadSerializer):
        repository = self.get_repo()
        validate_activated_repo(repository)
        commit = self.get_commit(repository)
        report = self.get_report(commit)
        version = (
            serializer.validated_data["version"]
            if "version" in serializer.validated_data
            else None
        )
        log.info(
            "Request to create new upload",
            extra=dict(
                repo=repository.name,
                commit=commit.commitid,
                cli_version=version,
            ),
        )
        if version:
            metrics.incr("upload.cli." + f"{version}")
        archive_service = ArchiveService(repository)
        instance: ReportSession = serializer.save(
            report_id=report.id,
            upload_extras={"format_version": "v1"},
        )

        # only Shelter requests are allowed to set their own `storage_path`
        if instance.storage_path is None or not self.is_shelter_request():
            path = MinioEndpoints.raw_with_upload_id.get_path(
                version="v4",
                date=timezone.now().strftime("%Y-%m-%d"),
                repo_hash=archive_service.storage_hash,
                commit_sha=commit.commitid,
                reportid=report.external_id,
                uploadid=instance.external_id,
            )
            instance.storage_path = path
            instance.save()
        self.trigger_upload_task(repository, commit.commitid, instance, report)
        metrics.incr("uploads.accepted", 1)
        self.activate_repo(repository)
        self.send_analytics_data(commit, instance, version)
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
                commit=commit_sha,
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
        if (
            repository.activated
            and repository.active
            and not repository.deleted
            and repository.coverage_enabled
        ):
            return
        repository.activated = True
        repository.active = True
        repository.deleted = False
        repository.coverage_enabled = True
        repository.save(
            update_fields=[
                "activated",
                "active",
                "deleted",
                "coverage_enabled",
                "updatestamp",
            ]
        )

    def send_analytics_data(self, commit: Commit, upload: ReportSession, version):
        token = self.get_token(commit)
        analytics_upload_data = {
            "commit": commit.commitid,
            "branch": commit.branch,
            "pr": commit.pullid,
            "repo": commit.repository.name,
            "repository_name": commit.repository.name,
            "repository_id": commit.repository.repoid,
            "service": commit.repository.service,
            "build": upload.build_code,
            "build_url": upload.build_url,
            # we were previously using upload.flag_names here, and this query might not be optimized
            # we weren't doing it in the legacy endpoint, but in the new one we are, and it may be causing problems
            # therefore we are removing this for now to see if it is the source of the issue
            "flags": "",
            "owner": commit.repository.author.ownerid,
            "token": str(token),
            "version": version,
            "uploader_type": "CLI",
        }
        AnalyticsService().account_uploaded_coverage_report(
            commit.repository.author.ownerid, analytics_upload_data
        )

    def get_token(self, commit: Commit):
        repo = commit.repository
        if isinstance(self.request.auth, TokenlessAuth):
            token = "tokenless_upload"
        elif isinstance(self.request.auth, OrgLevelTokenRepositoryAuth):
            token = (
                OrganizationLevelToken.objects.filter(owner=repo.author).first().token
            )
        else:
            token = repo.upload_token
        return token

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
