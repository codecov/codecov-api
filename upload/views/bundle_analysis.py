import logging
import uuid
from typing import Any, Callable

from django.conf import settings
from django.http import HttpRequest
from rest_framework import serializers, status
from rest_framework.exceptions import NotAuthenticated, NotFound
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from shared.api_archive.archive import ArchiveService
from shared.bundle_analysis.storage import StoragePaths, get_bucket_name
from shared.metrics import Counter, inc_counter

from codecov_auth.authentication.repo_auth import (
    BundleAnalysisTokenlessAuthentication,
    GitHubOIDCTokenAuthentication,
    OrgLevelTokenAuthentication,
    RepositoryLegacyTokenAuthentication,
    UploadTokenRequiredGetFromBodyAuthenticationCheck,
    repo_auth_custom_exception_handler,
)
from codecov_auth.authentication.types import RepositoryAsUser
from codecov_auth.models import Owner, Service
from core.models import Commit
from reports.models import CommitReport
from services.redis_configuration import get_redis_connection
from timeseries.models import Dataset, MeasurementName
from upload.helpers import (
    dispatch_upload_task,
    generate_upload_prometheus_metrics_labels,
)
from upload.views.base import ShelterMixin
from upload.views.helpers import get_repository_from_string

log = logging.getLogger(__name__)


BUNDLE_ANALYSIS_UPLOAD_VIEWS_COUNTER = Counter(
    "bundle_analysis_upload_views_runs",
    "Number of times a BA upload was run and with what result",
    [
        "agent",
        "version",
        "action",
        "endpoint",
        "is_using_shelter",
        "position",
    ],
)


class UploadBundleAnalysisPermission(BasePermission):
    def has_permission(self, request: HttpRequest, view: Any) -> bool:
        return request.auth is not None and "upload" in request.auth.get_scopes()


class UploadSerializer(serializers.Serializer):
    commit = serializers.CharField(required=True)
    slug = serializers.CharField(required=True)
    build = serializers.CharField(required=False, allow_null=True)
    buildURL = serializers.CharField(required=False, allow_null=True)
    job = serializers.CharField(required=False, allow_null=True)
    pr = serializers.CharField(required=False, allow_null=True)
    service = serializers.CharField(required=False, allow_null=True)
    branch = serializers.CharField(required=False, allow_null=True)
    compareSha = serializers.CharField(required=False, allow_null=True)
    git_service = serializers.CharField(required=False, allow_null=True)
    storage_path = serializers.CharField(required=False, allow_null=True)
    upload_external_id = serializers.CharField(required=False, allow_null=True)


class BundleAnalysisView(APIView, ShelterMixin):
    permission_classes = [UploadBundleAnalysisPermission]
    authentication_classes = [
        UploadTokenRequiredGetFromBodyAuthenticationCheck,
        OrgLevelTokenAuthentication,
        GitHubOIDCTokenAuthentication,
        RepositoryLegacyTokenAuthentication,
        BundleAnalysisTokenlessAuthentication,
    ]

    def get_exception_handler(self) -> Callable:
        return repo_auth_custom_exception_handler

    def post(self, request: HttpRequest) -> Response:
        labels = generate_upload_prometheus_metrics_labels(
            action="bundle_analysis",
            endpoint="bundle_analysis",
            request=self.request,
            is_shelter_request=self.is_shelter_request(),
            position="start",
            include_empty_labels=False,
        )
        inc_counter(
            BUNDLE_ANALYSIS_UPLOAD_VIEWS_COUNTER,
            labels=labels,
        )

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

        if repo is None:
            raise NotFound("Repository not found.")

        update_fields = []
        if not repo.active or not repo.activated:
            repo.active = True
            repo.activated = True
            update_fields += ["active", "activated"]

        if not repo.bundle_analysis_enabled:
            repo.bundle_analysis_enabled = True
            update_fields += ["bundle_analysis_enabled"]

        if update_fields:
            repo.save(update_fields=update_fields)

        commit, _ = Commit.objects.get_or_create(
            commitid=data["commit"],
            repository=repo,
            defaults={
                "branch": data.get("branch"),
                "pullid": data.get("pr"),
                "merged": False if data.get("pr") is not None else None,
                "state": "pending",
            },
        )

        storage_path = data.get("storage_path", None)
        upload_external_id = data.get("upload_external_id", None)
        url = None
        if not self.is_shelter_request():
            upload_external_id = str(uuid.uuid4())
            storage_path = StoragePaths.upload.path(upload_key=upload_external_id)
            archive_service = ArchiveService(repo)
            url = archive_service.storage.create_presigned_put(
                get_bucket_name(), storage_path, 30
            )

        task_arguments = {
            # these are used in the upload task when saving an upload record
            # and use some unfortunately named and confusing keys
            # (eventual reports_upload columns indicated by comments)
            "reportid": upload_external_id,  # external_id
            "build": data.get("build"),  # build_code
            "build_url": data.get("buildURL"),  # build_url
            "job": data.get("job"),  # job_code
            "service": data.get("service"),  # provider
            "url": storage_path,  # storage_path
            # these are used for dispatching the task below
            "commit": commit.commitid,
            "report_code": None,
            # custom comparison sha for the current uploaded commit sha
            "bundle_analysis_compare_sha": data.get("compareSha"),
        }

        log.info(
            "Dispatching bundle analysis upload to worker",
            extra=dict(
                commit=commit.commitid,
                repoid=repo.repoid,
                task_arguments=task_arguments,
            ),
        )
        labels = generate_upload_prometheus_metrics_labels(
            action="bundle_analysis",
            endpoint="bundle_analysis",
            request=self.request,
            is_shelter_request=self.is_shelter_request(),
            position="end",
            include_empty_labels=False,
        )
        inc_counter(
            BUNDLE_ANALYSIS_UPLOAD_VIEWS_COUNTER,
            labels=labels,
        )

        dispatch_upload_task(
            task_arguments,
            repo,
            get_redis_connection(),
            report_type=CommitReport.ReportType.BUNDLE_ANALYSIS,
        )

        if settings.TIMESERIES_ENABLED:
            supported_bundle_analysis_measurement_types = [
                MeasurementName.BUNDLE_ANALYSIS_ASSET_SIZE,
                MeasurementName.BUNDLE_ANALYSIS_FONT_SIZE,
                MeasurementName.BUNDLE_ANALYSIS_IMAGE_SIZE,
                MeasurementName.BUNDLE_ANALYSIS_JAVASCRIPT_SIZE,
                MeasurementName.BUNDLE_ANALYSIS_REPORT_SIZE,
                MeasurementName.BUNDLE_ANALYSIS_STYLESHEET_SIZE,
            ]
            for measurement_type in supported_bundle_analysis_measurement_types:
                _, created = Dataset.objects.get_or_create(
                    name=measurement_type.value,
                    repository_id=repo.pk,
                )
                if created:
                    log.info(
                        "Created new timescale dataset for bundle analysis",
                        extra=dict(
                            commit=commit.commitid,
                            repoid=repo.repoid,
                            measurement_type=measurement_type,
                        ),
                    )

        return Response({"url": url}, status=201)
