import logging
import uuid

from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from sentry_sdk import metrics

from codecov_auth.authentication.repo_auth import (
    GitHubOIDCTokenAuthentication,
    OrgLevelTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
    TokenlessAuthentication,
    repo_auth_custom_exception_handler,
)
from codecov_auth.authentication.types import RepositoryAsUser
from codecov_auth.models import Owner, Service
from core.models import Commit
from reports.models import CommitReport
from services.archive import ArchiveService, MinioEndpoints
from services.redis_configuration import get_redis_connection
from upload.helpers import dispatch_upload_task, generate_upload_sentry_metrics_tags
from upload.serializers import FlagListField
from upload.views.base import ShelterMixin
from upload.views.helpers import get_repository_from_string

log = logging.getLogger(__name__)


class UploadTestResultsPermission(BasePermission):
    def has_permission(self, request, view):
        return request.auth is not None and "upload" in request.auth.get_scopes()


class UploadSerializer(serializers.Serializer):
    commit = serializers.CharField(required=True)
    slug = serializers.CharField(required=True)
    build = serializers.CharField(required=False)
    buildURL = serializers.CharField(required=False)
    job = serializers.CharField(required=False)
    flags = FlagListField(required=False)
    pr = serializers.CharField(required=False)
    branch = serializers.CharField(required=False, allow_null=True)
    service = serializers.CharField(required=False)
    storage_path = serializers.CharField(required=False)


class TestResultsView(
    APIView,
    ShelterMixin,
):
    permission_classes = [UploadTestResultsPermission]
    authentication_classes = [
        OrgLevelTokenAuthentication,
        GitHubOIDCTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
        TokenlessAuthentication,
    ]

    def get_exception_handler(self):
        return repo_auth_custom_exception_handler

    def post(self, request):
        serializer = UploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data

        if isinstance(request.user, Owner):
            # using org token
            owner = request.user
            repo = get_repository_from_string(Service(owner.service), data["slug"])
        elif isinstance(request.user, RepositoryAsUser):
            # repository token
            repo = request.user._repository
        else:
            raise NotAuthenticated()

        update_fields = []
        if not repo.active or not repo.activated:
            repo.active = True
            repo.activated = True
            update_fields += ["active", "activated"]

        if not repo.test_analytics_enabled:
            repo.test_analytics_enabled = True
            update_fields += ["test_analytics_enabled"]

        if update_fields:
            repo.save(update_fields=update_fields)

        metrics.incr(
            "upload",
            tags=generate_upload_sentry_metrics_tags(
                action="test_results",
                endpoint="test_results",
                request=request,
                repository=repo,
                is_shelter_request=self.is_shelter_request(),
            ),
        )

        commit, _ = Commit.objects.get_or_create(
            commitid=data["commit"],
            repository=repo,
            defaults={
                "branch": data.get("branch") or repo.branch,
                "pullid": data.get("pr"),
                "merged": False if data.get("pr") is not None else None,
                "state": "pending",
            },
        )

        upload_external_id = str(uuid.uuid4())

        archive_service = ArchiveService(repo)

        storage_path = data.get("storage_path", None)
        if storage_path is None or not self.is_shelter_request():
            storage_path = MinioEndpoints.test_results.get_path(
                date=timezone.now().strftime("%Y-%m-%d"),
                repo_hash=archive_service.get_archive_hash(repo),
                commit_sha=data["commit"],
                uploadid=upload_external_id,
            )

        url = archive_service.create_presigned_put(storage_path)

        task_arguments = {
            # these are used in the upload task when saving an upload record
            # and use some unfortunately named and confusing keys
            # (eventual reports_upload columns indicated by comments)
            "reportid": upload_external_id,  # external_id
            "build": data.get("build"),  # build_code
            "build_url": data.get("buildURL"),  # build_url
            "job": data.get("job"),  # job_code
            "flags": data.get("flags"),
            "service": data.get("service"),  # provider
            "url": storage_path,  # storage_path
            # these are used for dispatching the task below
            "commit": commit.commitid,
            "report_code": None,
        }

        log.info(
            "Dispatching test results upload to worker",
            extra=dict(
                commit=commit.commitid,
                repoid=repo.repoid,
                task_arguments=task_arguments,
            ),
        )

        dispatch_upload_task(
            task_arguments,
            repo,
            get_redis_connection(),
            report_type=CommitReport.ReportType.TEST_RESULTS,
        )

        return Response({"raw_upload_location": url}, status=201)
