import logging

from django.http import HttpRequest, HttpResponseNotAllowed
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import BasePermission
from shared.metrics import inc_counter
from shared.upload.utils import UploaderType, insert_coverage_measurement

from codecov_auth.authentication.repo_auth import (
    GitHubOIDCTokenAuthentication,
    GlobalTokenAuthentication,
    OIDCTokenRepositoryAuth,
    OrgLevelTokenAuthentication,
    OrgLevelTokenRepositoryAuth,
    RepositoryLegacyTokenAuthentication,
    TokenlessAuth,
    TokenlessAuthentication,
    UploadTokenRequiredAuthenticationCheck,
    repo_auth_custom_exception_handler,
)
from codecov_auth.models import OrganizationLevelToken
from core.models import Commit, Repository
from reports.models import CommitReport, ReportSession
from services.analytics import AnalyticsService
from services.archive import ArchiveService, MinioEndpoints
from services.redis_configuration import get_redis_connection
from upload.helpers import (
    dispatch_upload_task,
    generate_upload_prometheus_metrics_labels,
    validate_activated_repo,
)
from upload.metrics import API_UPLOAD_COUNTER
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


class UploadLogicMixin:
    def create_upload(self, serializer, repository, commit, report):
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
        archive_service = ArchiveService(repository)
        # Create upload record
        instance: ReportSession = serializer.save(
            report_id=report.id,
            upload_extras={"format_version": "v1"},
        )

        # Inserts mirror upload record into measurements table. CLI hits this endpoint
        insert_coverage_measurement(
            owner_id=repository.author.ownerid,
            repo_id=repository.repoid,
            commit_id=commit.id,
            upload_id=instance.id,
            uploader_used=UploaderType.CLI.value,
            private_repo=repository.private,
            report_type=report.report_type,
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
        self.activate_repo(repository)
        self.send_analytics_data(commit, instance, version)
        return instance

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
        token = self.get_token_for_analytics(commit)
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

    def get_token_for_analytics(self, commit: Commit):
        repo = commit.repository
        if isinstance(self.request.auth, TokenlessAuth):
            token = "tokenless_upload"
        elif isinstance(self.request.auth, OrgLevelTokenRepositoryAuth):
            token = (
                OrganizationLevelToken.objects.filter(owner=repo.author).first().token
            )
        elif isinstance(self.request.auth, OIDCTokenRepositoryAuth):
            token = "oidc_token_upload"
        else:
            token = repo.upload_token
        return token


class UploadViews(ListCreateAPIView, GetterMixin, UploadLogicMixin):
    serializer_class = UploadSerializer
    permission_classes = [
        CanDoCoverageUploadsPermission,
    ]
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

    def perform_create(self, serializer: UploadSerializer):
        inc_counter(
            API_UPLOAD_COUNTER,
            labels=generate_upload_prometheus_metrics_labels(
                action="coverage",
                endpoint="create_upload",
                request=self.request,
                is_shelter_request=self.is_shelter_request(),
                position="start",
            ),
        )
        repository: Repository = self.get_repo()
        validate_activated_repo(repository)
        commit: Commit = self.get_commit(repository)
        report: CommitReport = self.get_report(commit)

        instance = self.create_upload(serializer, repository, commit, report)
        inc_counter(
            API_UPLOAD_COUNTER,
            labels=generate_upload_prometheus_metrics_labels(
                action="coverage",
                endpoint="create_upload",
                request=self.request,
                repository=repository,
                is_shelter_request=self.is_shelter_request(),
                position="end",
            ),
        )

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

    def get_repo(self) -> Repository:
        try:
            repo = super().get_repo()
            return repo
        except ValidationError as exception:
            raise exception

    def get_commit(self, repo: Repository) -> Commit:
        try:
            commit = super().get_commit(repo)
            return commit
        except ValidationError as excpetion:
            raise excpetion

    def get_report(self, commit: Commit) -> CommitReport:
        try:
            report = super().get_report(commit)
            return report
        except ValidationError as exception:
            raise exception
