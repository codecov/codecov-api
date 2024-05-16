import asyncio
import logging
import re
from contextlib import suppress
from datetime import datetime
from json import dumps
from uuid import uuid4

import minio
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import MultipleObjectsReturned
from django.http import Http404, HttpResponse, HttpResponseServerError
from django.utils import timezone
from django.utils.decorators import classonlymethod
from django.utils.encoding import smart_str
from django.views import View
from rest_framework import renderers, status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from sentry_sdk import metrics as sentry_metrics
from shared.metrics import metrics

from codecov.db import sync_to_async
from codecov_auth.commands.owner import OwnerCommands
from core.commands.repository import RepositoryCommands
from services.analytics import AnalyticsService
from services.archive import ArchiveService
from services.redis_configuration import get_redis_connection
from upload.helpers import (
    check_commit_upload_constraints,
    determine_repo_for_upload,
    determine_upload_branch_to_use,
    determine_upload_commit_to_use,
    determine_upload_pr_to_use,
    dispatch_upload_task,
    generate_upload_sentry_metrics_tags,
    insert_commit,
    parse_headers,
    parse_params,
    store_report_in_redis,
    validate_upload,
)
from upload.views.base import ShelterMixin
from utils.config import get_config
from utils.services import get_long_service_name

log = logging.getLogger(__name__)


class PlainTextRenderer(renderers.BaseRenderer):
    media_type = "text/plain"
    format = "txt"

    def render(self, data, media_type=None, renderer_context=None):
        return smart_str(data, encoding=self.charset)


class UploadHandler(APIView, ShelterMixin):
    permission_classes = [AllowAny]
    renderer_classes = [PlainTextRenderer, renderers.JSONRenderer]

    def get(self, request, *args, **kwargs):
        return HttpResponse(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def options(self, request, *args, **kwargs):
        response = HttpResponse()
        response["Accept"] = "text/*"
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Method"] = "POST"
        response["Access-Control-Allow-Headers"] = (
            "Origin, Content-Type, Accept, X-User-Agent"
        )

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
        response["Access-Control-Allow-Headers"] = (
            "Origin, Content-Type, Accept, X-User-Agent"
        )

        # Parse request parameters
        request_params = {
            **self.request.query_params.dict(),  # query_params is a QueryDict, need to convert to dict to process it properly
            **self.kwargs,
        }
        request_params["token"] = request_params.get("token") or request.META.get(
            "HTTP_X_UPLOAD_TOKEN"
        )

        package = request_params.get("package")
        if package is not None:
            package_format = r"((codecov-cli/)|((.+-)?uploader-))(\d+.\d+.\d+)"
            match = re.fullmatch(package_format, package)
            if match:
                if match.group(2):  # Matches codecov-cli/
                    metrics.incr(f"upload.cli.{match.group(5)}")
                else:  # Matches (.+-)?uploader-
                    metrics.incr(f"upload.uploader.{match.group(5)}")
            else:
                log.warning(
                    "Package query parameter failed to match CLI or uploader format",
                    extra=dict(package=package),
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

        # Try to determine the repository associated with the upload based on the params provided
        try:
            repository = determine_repo_for_upload(upload_params)
            owner = repository.author
        except ValidationError as e:
            response.status_code = status.HTTP_400_BAD_REQUEST
            response.content = "Could not determine repo and owner"
            metrics.incr("uploads.rejected", 1)
            return response
        except MultipleObjectsReturned as e:
            response.status_code = status.HTTP_400_BAD_REQUEST
            response.content = "Found too many repos"
            metrics.incr("uploads.rejected", 1)
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

        sentry_tags = generate_upload_sentry_metrics_tags(
            action="coverage",
            endpoint="legacy_upload",
            request=self.request,
            repository=repository,
            is_shelter_request=self.is_shelter_request(),
        )

        sentry_metrics.incr(
            "upload",
            tags=sentry_tags,
        )

        sentry_metrics.set(
            "upload_set",
            repository.author.ownerid,
            tags=sentry_tags,
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
        destination_url = f"{settings.CODECOV_DASHBOARD_URL}/{owner.service}/{owner.username}/{repository.name}/commit/{commitid}"

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

            # only Shelter requests are allowed to set their own `storage_path`
            path = upload_params.get("storage_path")
            if path is None or not self.is_shelter_request():
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
                metrics.incr("uploads.rejected", 1)
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
            "url": (
                path
                if path  # If a path was generated for a v4 upload, pass that to the 'url' field, potentially overwriting it
                else upload_params.get("url")
            ),
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

        # Analytics Tracking
        analytics_upload_data = upload_params.copy()
        analytics_upload_data["repository_id"] = repository.repoid
        analytics_upload_data["repository_name"] = repository.name
        analytics_upload_data["version"] = version
        analytics_upload_data["userid_type"] = "org"
        analytics_upload_data["uploader_type"] = "node uploader"
        AnalyticsService().account_uploaded_coverage_report(
            owner.ownerid, analytics_upload_data
        )

        if version == "v4":
            response["Content-Type"] = "text/plain"
            request.META["HTTP_ACCEPT"] = "text/plain"
        if version == "v2":
            response["Content-Type"] = "application/json"

        response.status_code = status.HTTP_200_OK
        metrics.incr("uploads.accepted", 1)
        return response


class UploadDownloadHandler(View):
    @classonlymethod
    def as_view(_, **initkwargs):
        view = super().as_view(**initkwargs)
        view._is_coroutine = asyncio.coroutines._is_coroutine
        return view

    async def get_repo(self):
        owner = await OwnerCommands(
            self.request.current_owner, self.service
        ).fetch_owner(self.owner_username)
        if owner is None:
            raise Http404("Requested report could not be found")
        repo = await RepositoryCommands(
            self.request.current_owner, self.service
        ).fetch_repository(owner, self.repo_name)
        if repo is None:
            raise Http404("Requested report could not be found")
        return repo

    def validate_path(self, repo):
        msg = "Requested report could not be found"
        if not self.path:
            raise Http404(msg)

        if self.path.startswith("v4/raw"):
            # direct API upload

            # Verify that the repo hash in the path matches the repo in the URL by generating the repo hash
            archive_service = ArchiveService(repo)
            if archive_service.storage_hash not in self.path:
                raise Http404(msg)
        elif self.path.startswith("shelter/"):
            # Shelter upload
            if not self.path.startswith(
                f"shelter/{self.service}/{self.owner_username}::::{self.repo_name}"
            ):
                raise Http404(msg)
        else:
            # unexpected path structure
            raise Http404(msg)

    def read_params(self):
        self.path = self.request.GET.get("path")
        self.service = get_long_service_name(self.kwargs.get("service"))
        self.repo_name = self.kwargs.get("repo_name")
        self.owner_username = self.kwargs.get("owner_username")

    @sync_to_async
    def get_presigned_url(self, repo):
        archive_service = ArchiveService(repo)

        try:
            return archive_service.storage.create_presigned_get(
                archive_service.root, self.path, expires=30
            )
        except minio.error.S3Error as e:
            if e.code == "NoSuchKey":
                raise Http404("Requested report could not be found")
            else:
                raise

    async def get(self, request, *args, **kwargs):
        await self._get_user(request)

        self.read_params()
        repo = await self.get_repo()
        self.validate_path(repo)

        response = HttpResponse(status=302)
        response["Location"] = await self.get_presigned_url(repo)
        return response

    @sync_to_async
    def _get_user(self, request):
        # force eager evaluation of `request.user` (a lazy object)
        # while we're in a sync context
        if request.user:
            request.user.pk
