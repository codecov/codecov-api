import logging

from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseNotAllowed,
    HttpResponseNotFound,
    HttpResponseServerError,
)
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny, BasePermission
from shared.metrics import metrics

from codecov_auth.authentication.repo_auth import RepositoryTokenAuthentication
from core.models import Repository
from services.archive import ArchiveService
from upload.helpers import determine_repo_for_upload, parse_params
from upload.serializers import UploadSerializer
from upload.throttles import UploadsPerCommitThrottle, UploadsPerWindowThrottle

log = logging.getLogger(__name__)


class CanDoCoverageUploadsPermission(BasePermission):
    def has_permission(self, request, view):
        return request.auth is not None and "upload" in request.auth.get_scopes()


class UploadViews(ListCreateAPIView):
    serializer_class = UploadSerializer
    permission_classes = [
        AllowAny,
    ]
    throttle_classes = [UploadsPerCommitThrottle, UploadsPerWindowThrottle]

    def create(self, request: HttpRequest, repo: str, commit_id: str, report_id: str):
        log.info(
            "Request to create new upload",
            extra=dict(repo=repo, commit_id=commit_id, report_id=report_id),
        )
        return HttpResponseNotFound(f"Not available")

    def list(self, request: HttpRequest, repo: str, commit_id: str, report_id: str):
        return HttpResponseNotAllowed(permitted_methods=["POST"])

    def _get_response_with_headers(self):
        # Set response headers
        response = HttpResponse()
        response["Access-Control-Allow-Origin"] = "*"
        response[
            "Access-Control-Allow-Headers"
        ] = "Origin, Content-Type, Accept, X-User-Agent"
        return response

    def _generate_presigned_put(
        self, repository: Repository, commitid: str, reportid: str, *args, **kwargs
    ):
        # TODO: differentiate presigned puts of normal upload reports and mutation testing uplaod reports
        archive_service = ArchiveService(repository)
        try:
            upload_url = archive_service.create_raw_upload_presigned_put(
                commit_sha=commitid, filename="{}.txt".format(reportid)
            )
            log.info(
                "Returning presign put",
                extra=dict(
                    commit=commitid, repoid=repository.repoid, upload_url=upload_url
                ),
            )
            return upload_url
        except Exception as e:
            log.warning(
                f"Error generating minio presign put {e}",
                extra=dict(
                    commit=commitid,
                    pr=kwargs.get("pr", "unknown"),
                    branch=kwargs.get("branch", "unknown"),
                    version=kwargs.get("version", "unknown"),
                    upload_params=kwargs.get("upload_params", "unknown"),
                ),
            )
        return None


class MutationTestingUploadView(UploadViews):
    authentication_classes = [RepositoryTokenAuthentication]

    def create(self, request: HttpRequest, repo: str, commit_id: str, report_id: str):
        log.info(
            "request to create new mutation test upload",
            extra=dict(repo=repo, commit_id=commit_id, report_id=report_id),
        )
        response = self._get_response_with_headers()

        # Parse upload params
        # Not sure why we have to do this, or if it can be dropped, but seems important in the old endpoint
        # REVIEW: verify if we really need this here
        request_params = {
            **request.query_params.dict(),  # query_params is a QueryDict, need to convert to dict to process it properly
            **self.kwargs,
        }
        request_params["token"] = request_params.get("token") or request.META.get(
            "HTTP_X_UPLOAD_TOKEN"
        )
        try:
            # note: try to avoid mutating upload_params past this point, to make it easier to reason about the state of this variable
            upload_params = parse_params(request_params)
        except ValidationError as e:
            log.warning(
                "Failed to parse upload request params",
                extra=dict(request_params=request_params, errors=str(e)),
            )
            response.status_code = status.HTTP_400_BAD_REQUEST
            response.content = "Invalid request parameters"
            metrics.incr("uploads.rejected", 1)
            return response

        # Verify that the repo exists and the upload token is for that repo
        # FIXME: THere will be a separate function for validating the uplaod token, probably (CODE-1559)
        try:
            # FIXME: There will probably be a new function for getting the repo as well
            repo_obj: Repository = determine_repo_for_upload(upload_params)
        except ValidationError as e:
            response.status_code = status.HTTP_400_BAD_REQUEST
            response.content = "Could not determine repo and owner"
            metrics.incr("uploads.rejected", 1)
            return response

        # TEMP - Only codecov repos can uplaod mutation testing reports for now
        # REVIEW: check how to make this verification
        log.warning(repo_obj)
        if not (
            repo_obj.author.name.lower() == "codecov"
            or repo_obj.author.username.lower() == "codecov"
        ):
            response.status_code = status.HTTP_403_FORBIDDEN
            response.content = "Feature currently unnavailable outside codecov"
            return response

        # Complete kwargs for debugging purposes. Info can be extracted from commit and repo
        upload_url = self._generate_presigned_put(repo_obj, commit_id, report_id)
        if upload_url is None:
            metrics.incr("uploads.rejected", 1)
            return HttpResponseServerError("Unknown error, please try again later")

        # TODO:
        # Send task to worker
        # dispatch_upload_task(task_arguments, repository, redis)

        # TODO: Segment Tracking.
        # segment_upload_data = upload_params.copy()
        # segment_upload_data["repository_id"] = repository.repoid
        # segment_upload_data["repository_name"] = repository.name
        # segment_upload_data["version"] = version
        # segment_upload_data["userid_type"] = "org"
        # SegmentService().account_uploaded_coverage_report(
        #     owner.ownerid, segment_upload_data
        # )
        response.status_code = status.HTTP_200_OK
        response.content = upload_url
        metrics.incr("uploads.accepted", 1)
        return response
