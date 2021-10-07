import asyncio
import logging
from contextlib import suppress
from datetime import datetime
from json import dumps
from urllib.parse import parse_qs
from uuid import uuid4

import minio
from asgiref.sync import sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.http import Http404, HttpResponse, HttpResponseServerError
from django.utils import timezone
from django.utils.decorators import classonlymethod
from django.utils.encoding import smart_text
from django.views import View
from rest_framework import renderers, status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from codecov_auth.authentication import CodecovTokenAuthentication
from codecov_auth.commands.owner import OwnerCommands
from core.commands.repository import RepositoryCommands
from services.archive import ArchiveService
from services.redis_configuration import get_redis_connection
from services.segment import SegmentService
from utils.config import get_config
from utils.services import get_long_service_name

from .helpers import (
    check_commit_upload_constraints,
    determine_repo_for_upload,
    determine_upload_branch_to_use,
    determine_upload_commit_to_use,
    determine_upload_pr_to_use,
    dispatch_upload_task,
    insert_commit,
    parse_headers,
    parse_params,
    store_report_in_redis,
    validate_upload,
)

log = logging.getLogger(__name__)


class PlainTextRenderer(renderers.BaseRenderer):
    media_type = "text/plain"
    format = "txt"

    def render(self, data, media_type=None, renderer_context=None):
        return smart_text(data, encoding=self.charset)


class UploadHandler(APIView):
    permission_classes = [AllowAny]
    renderer_classes = [PlainTextRenderer, renderers.JSONRenderer]

    def get(self, request, *args, **kwargs):
        return HttpResponse(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def options(self, request, *args, **kwargs):
        response = HttpResponse()
        response["Accept"] = "text/*"
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Method"] = "POST"
        response[
            "Access-Control-Allow-Headers"
        ] = "Origin, Content-Type, Accept, X-User-Agent"

        return response

    def post(self, request, *args, **kwargs):
        # Extract the version
        version = self.kwargs["version"]

        log.info(
            f"Received upload request {version}",
            extra=dict(
                version=version,
                query_params=self.request.query_params,
                commit=self.request.query_params.get("commit"),
            ),
        )

        # Set response headers
        response = HttpResponse()
        response["Access-Control-Allow-Origin"] = "*"
        response[
            "Access-Control-Allow-Headers"
        ] = "Origin, Content-Type, Accept, X-User-Agent"

        # Parse request parameters
        request_params = {
            **self.request.query_params.dict(),  # query_params is a QueryDict, need to convert to dict to process it properly
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
            return response

        # Try to determine the repository associated with the upload based on the params provided
        try:
            repository = determine_repo_for_upload(upload_params)
            owner = repository.author
        except ValidationError as e:
            response.status_code = status.HTTP_400_BAD_REQUEST
            response.content = "Could not determine repo and owner"
            return response

        log.info(
            "Found repository for upload request",
            extra=dict(
                version=version,
                upload_params=upload_params,
                repo_name=repository.name,
                owner_username=owner.username,
                commit=upload_params.get("commit"),
            ),
        )

        # Validate the upload to make sure the org has enough repo credits and is allowed to upload for this commit
        redis = get_redis_connection()
        validate_upload(upload_params, repository, redis)
        log.info(
            "Upload was determined to be valid", extra=dict(repoid=repository.repoid)
        )
        # Do some processing to handle special cases for branch, pr, and commit values, and determine which values to use
        # note that these values may be different from the values provided in the upload_params
        branch = determine_upload_branch_to_use(upload_params, repository.branch)
        pr = determine_upload_pr_to_use(upload_params)
        commitid = determine_upload_commit_to_use(upload_params, repository)

        # Save (or update, if it exists already) the commit in the database
        log.info(
            "Saving commit in database",
            extra=dict(
                commit=commitid,
                pr=pr,
                branch=branch,
                version=version,
                upload_params=upload_params,
            ),
        )
        commit = insert_commit(
            commitid, branch, pr, repository, owner, upload_params.get("parent")
        )
        check_commit_upload_constraints(commit)

        # --------- Handle the actual upload

        reportid = str(uuid4())
        path = None  # populated later for v4 uploads when generating presigned PUT url
        redis_key = None  # populated later for v2 uploads when storing report in Redis

        # Get the url where the commit details can be found on the Codecov site, we'll return this in the response
        destination_url = f"{get_config('setup', 'codecov_url', default='https://codecov.io')}/{owner.service}/{owner.username}/{repository.name}/commit/{commitid}"

        # v2 - store request body in redis
        if version == "v2":
            log.info(
                "Started V2 upload",
                extra=dict(
                    commit=commitid,
                    pr=pr,
                    branch=branch,
                    version=version,
                    upload_params=upload_params,
                ),
            )
            redis_key = store_report_in_redis(request, commitid, reportid, redis)

            log.info(
                "Stored coverage report in redis",
                extra=dict(
                    commit=commitid,
                    upload_params=upload_params,
                    reportid=reportid,
                    redis_key=redis_key,
                    repoid=repository.repoid,
                ),
            )

            response.write(
                dumps(
                    dict(
                        message="Coverage reports upload successfully",
                        uploaded=True,
                        queued=True,
                        id=reportid,
                        url=destination_url,
                    )
                )
            )

        # v4 - generate presigned PUT url
        minio = get_config("services", "minio") or {}
        if minio and version == "v4":

            log.info(
                "Started V4 upload",
                extra=dict(
                    commit=commitid,
                    pr=pr,
                    branch=branch,
                    version=version,
                    upload_params=upload_params,
                ),
            )

            headers = parse_headers(request.META, upload_params)

            archive_service = ArchiveService(repository)
            path = "/".join(
                (
                    "v4/raw",
                    timezone.now().strftime("%Y-%m-%d"),
                    archive_service.get_archive_hash(repository),
                    commitid,
                    f"{reportid}.txt",
                )
            )

            try:
                upload_url = archive_service.create_raw_upload_presigned_put(
                    commit_sha=commitid, filename="{}.txt".format(reportid)
                )
            except Exception as e:
                log.warning(
                    f"Error generating minio presign put {e}",
                    extra=dict(
                        commit=commitid,
                        pr=pr,
                        branch=branch,
                        version=version,
                        upload_params=upload_params,
                    ),
                )
                return HttpResponseServerError("Unknown error, please try again later")
            log.info(
                "Returning presign put",
                extra=dict(
                    commit=commitid, repoid=repository.repoid, upload_url=upload_url
                ),
            )
            response["Content-Type"] = "text/plain"
            response.write(f"{destination_url}\n{upload_url}")

        # Get build url
        if (
            repository.service == "gitlab_enterprise"
            and not upload_params.get("build_url")
            and upload_params.get("build")
        ):
            # if gitlab ci - change domain based by referer
            build_url = f"{get_config((repository.service, 'url'))}/{owner.username}/{repository.name}/{upload_params.get('build')}"
        else:
            build_url = upload_params.get("build_url")
        queue_params = upload_params.copy()
        if upload_params.get("using_global_token"):
            queue_params["service"] = request_params.get("service")
        # Define the task arguments to send when dispatching upload task to worker
        task_arguments = {
            **queue_params,
            "build_url": build_url,
            "reportid": reportid,
            "redis_key": redis_key,  # location of report for v2 uploads; this will be "None" for v4 uploads
            "url": path
            if path  # If a path was generated for a v4 upload, pass that to the 'url' field, potentially overwriting it
            else upload_params.get("url"),
            # These values below might be different from the initial request parameters, so overwrite them here to ensure they're up-to-date
            "commit": commitid,
            "branch": branch,
            "pr": pr,
        }

        log.info(
            "Dispatching upload to worker (new upload)",
            extra=dict(
                commit=commitid, task_arguments=task_arguments, repoid=repository.repoid
            ),
        )

        # Send task to worker
        dispatch_upload_task(task_arguments, repository, redis)

        # Segment Tracking
        segment_upload_data = upload_params.copy()
        segment_upload_data["repository_id"] = repository.repoid
        segment_upload_data["repository_name"] = repository.name
        segment_upload_data["version"] = version
        segment_upload_data["userid_type"] = "org"
        SegmentService().account_uploaded_coverage_report(
            owner.ownerid, segment_upload_data
        )

        if version == "v4":
            response["Content-Type"] = "text/plain"
            request.META["HTTP_ACCEPT"] = "text/plain"
        if version == "v2":
            response["Content-Type"] = "application/json"

        response.status_code = status.HTTP_200_OK
        return response


class UploadDownloadHandler(View):
    @sync_to_async
    def get_user(self, request):
        with suppress(APIException, TypeError):
            return CodecovTokenAuthentication().authenticate(request)[0]
        return AnonymousUser()

    @classonlymethod
    def as_view(_, **initkwargs):
        view = super().as_view(**initkwargs)
        view._is_coroutine = asyncio.coroutines._is_coroutine
        return view

    async def get_repo(self):
        owner = await OwnerCommands(self.request.user, self.service).fetch_owner(
            self.owner_username
        )
        if owner is None:
            raise Http404("Requested report could not be found")
        repo = await RepositoryCommands(
            self.request.user, self.service
        ).fetch_repository(owner, self.repo_name)
        if repo is None:
            raise Http404("Requested report could not be found")
        return repo

    def validate_path(self):
        if not self.path or "v4/raw" not in self.path:
            raise Http404("Requested report could not be found")

    def read_params(self):
        self.path = self.request.GET.get("path")
        self.service = get_long_service_name(self.kwargs.get("service"))
        self.repo_name = self.kwargs.get("repo_name")
        self.owner_username = self.kwargs.get("owner_username")

    @sync_to_async
    def get_from_storage(self, repo):
        archive_service = ArchiveService(repo)

        # Verify that the repo hash in the path matches the repo in the URL by generating the repo hash
        if archive_service.storage_hash not in self.path:
            raise Http404("Requested report could not be found")
        try:
            return archive_service.read_file(self.path)

        except minio.error.NoSuchKey as e:
            raise Http404("Requested report could not be found")

    async def get(self, request, *args, **kwargs):
        self.read_params()
        self.validate_path()
        request.user = await self.get_user(request)
        repo = await self.get_repo()
        raw_uploaded_report = await self.get_from_storage(repo)

        response = HttpResponse(raw_uploaded_report)
        response["Content-Type"] = "text/plain"
        return response
