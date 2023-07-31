import asyncio
import logging
import re
from datetime import timedelta
from json import dumps

from asgiref.sync import async_to_sync
from cerberus import Validator
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import NotFound, Throttled, ValidationError
from shared.reports.enums import UploadType
from shared.torngit.exceptions import TorngitClientError, TorngitObjectNotFoundError

from codecov_auth.models import Owner
from core.models import Commit, Repository
from plan.constants import USER_PLAN_REPRESENTATIONS
from reports.models import ReportSession
from services.repo_providers import RepoProviderService
from services.segment import SegmentService
from services.task import TaskService
from upload.tokenless.tokenless import TokenlessUploadHandler
from utils.config import get_config
from utils.encryption import encryptor

from .constants import ci, global_upload_token_providers

is_pull_noted_in_branch = re.compile(r".*(pull|pr)\/(\d+).*")

log = logging.getLogger(__name__)


def parse_params(data):
    """
    This function will validate the input request parameters and do some additional parsing/tranformation of the params.
    """

    # filter out empty values from the data; this makes parsing and setting defaults a bit easier
    non_empty_data = {
        key: value for key, value in data.items() if value not in [None, ""]
    }

    global_tokens = get_global_tokens()
    params_schema = {
        # --- The following parameters are populated in the code based on request data, settings, etc.
        "owner": {  # owner username, we set this by splitting the value of "slug" on "/" if provided
            "type": "string",
            "nullable": True,
            "default_setter": (
                lambda document: document.get("slug")
                .rsplit("/", 1)[0]
                .replace(
                    "/", ":"
                )  # we use ':' as separator for gitlab subgroups internally
                if document.get("slug")
                and len(document.get("slug").rsplit("/", 1)) == 2
                else None
            ),
        },
        # repo name, we set this by parsing the value of "slug" if provided
        "repo": {
            "type": "string",
            "nullable": True,
            "default_setter": (
                lambda document: document.get("slug").rsplit("/", 1)[1]
                if document.get("slug")
                and len(document.get("slug").rsplit("/", 1)) == 2
                else None
            ),
        },
        # indicates whether the token provided is a global upload token rather than a repository upload token
        # note: this needs to go before the "service" field in the schema so we can use is when determining the service value to use
        "using_global_token": {
            "type": "boolean",
            "default_setter": (
                lambda document: True
                if document.get("token") and document.get("token") in global_tokens
                else False
            ),
        },
        # --- The following parameters are expected to be provided in the upload request.
        "version": {"type": "string", "required": True, "allowed": ["v2", "v4"]},
        # commit SHA
        "commit": {
            "type": "string",
            "required": True,
            "regex": r"^\d+:\w{12}|\w{40}$",
            "coerce": lambda value: value.lower(),
        },
        # if this is true, then we won't do any merge commit parsing
        "_did_change_merge_commit": {"type": "boolean"},
        "slug": {"type": "string", "regex": r"^[\w\-\.\~\/]+\/[\w\-\.]{1,255}$"},
        # repository upload token
        "token": {
            "type": "string",
            "anyof": [
                {"regex": r"^[0-9a-f]{8}(-?[0-9a-f]{4}){3}-?[0-9a-f]{12}$"},
                {"allowed": list(global_tokens.keys())},
            ],
        },
        # name of the CI service used, must be a name in the list of CI services we support
        "service": {
            "type": "string",
            "nullable": True,
            "allowed": list(ci.keys()) + list(global_tokens.values()),
            "coerce": (
                lambda value: "travis" if value == "travis-org" else value,
            ),  # if "travis-org" was passed as the service rename it to "travis" before validating
            "default_setter": (
                lambda document: global_tokens[document.get("token")]
                if document.get("using_global_token")
                else None
            ),
        },
        # pull request number
        # if a value is passed to the "pull_request" field and not to "pr", we'll use that to set the value of this field
        "pr": {
            "type": "string",
            "regex": r"^(\d+|false|null|undefined|true)$",
            "nullable": True,
            "default_setter": (lambda document: document.get("pull_request")),
            "coerce": (
                lambda value: None if value in ["false", "null", "undefined"] else value
            ),
        },
        # pull request number
        # "deprecated" in the sense that if a value is passed to this field, we'll use it to set "pr" and use that field instead
        "pull_request": {  # pull request number
            "type": "string",
            "regex": r"^(\d+|false|null|undefined|true)$",
            "nullable": True,
            "coerce": (
                lambda value: None
                if value in ["false", "null", "undefined", "true"]
                else value
            ),
        },
        "build_url": {"type": "string", "regex": r"^https?\:\/\/(.{,200})"},
        "flags": {"type": "string", "regex": r"^[\w\.\-\,]+$"},
        "branch": {
            "type": "string",
            "nullable": True,
            "coerce": (
                lambda value: None
                if value == "HEAD"
                # if prefixed with "origin/" or "refs/heads", the prefix will be removed
                else value[7:]
                if value[:7] == "origin/"
                else value[11:]
                if value[:11] == "refs/heads/"
                else value,
            ),
        },
        "tag": {"type": "string"},
        # if a value is passed to "travis_job_id" and not to "job", we'll use that to set the value of this field
        "job": {
            "type": "string",
            "nullable": True,
            "default_setter": (lambda document: document.get("travis_job_id")),
        },
        # "deprecated" in the sense that if a value is passed to this field, we'll use it to set "job" and use that field instead
        "travis_job_id": {"type": "string", "nullable": True, "empty": True},
        "build": {
            "type": "string",
            "nullable": True,
            "coerce": (
                lambda value: None
                if value in ["null", "undefined", "none", "nil"]
                else value
            ),
        },
        "name": {"type": "string"},
        "package": {
            "type": "string",
            "regex": r"^(codecov-cli/|^(.+-)?uploader-)\d+.\d+.\d+$",
        },
        "s3": {"type": "integer"},
        "yaml": {
            "type": "string"
        },  # file path to custom location of codecov.yml in repo
        "url": {"type": "string"},  # custom location where report is found
        "parent": {"type": "string"},
        "project": {"type": "string"},
        "server_uri": {"type": "string"},
        "root": {"type": "string"},  # deprecated
    }

    v = Validator(params_schema, allow_unknown=True)
    if not v.validate(non_empty_data):
        raise ValidationError(v.errors)
    # override service to the one from the global token if global token is in use
    if v.document.get("using_global_token"):
        v.document["service"] = global_tokens[v.document.get("token")]
    # return validated data, including coerced values
    return v.document


def determine_repo_for_upload(upload_params):
    token = upload_params.get("token")
    using_global_token = upload_params.get("using_global_token")
    service = upload_params.get("service")

    if token and not using_global_token:
        try:
            repository = Repository.objects.get(upload_token=token)
        except ObjectDoesNotExist:
            raise NotFound(
                f"Could not find a repository associated with upload token {token}"
            )
    elif service:
        if using_global_token:
            git_service = service
        else:
            git_service = TokenlessUploadHandler(service, upload_params).verify_upload()
        try:
            repository = Repository.objects.get(
                author__service=git_service,
                name=upload_params.get("repo"),
                author__username=upload_params.get("owner"),
            )
        except ObjectDoesNotExist:
            raise NotFound(f"Could not find a repository, try using repo upload token")
    else:
        raise ValidationError(
            "Need either a token or service to determine target repository"
        )

    return repository

    """
    TODO: add CI verification and repo retrieval from CI
    elif service:
        if not using_global_token:
            # verify CI TODO
        
        # Get repo info from CI TODO
    """


def determine_upload_branch_to_use(upload_params, repo_default_branch):
    """
    Do processing on the upload request parameters to determine which branch to use for the upload:
    - If no branch or PR were provided, use the default branch for the repository.
    - If a branch was provided and the branch name contains "pull" or "pr" followed by digits, don't use the branch name.
    In "determine_upload_pr_to_use" we'll extract the digits from the branch name and use that as the pr number.
    - Otherwise, use the value provided in the request parameters.
    """
    upload_params_branch = upload_params.get("branch")
    upload_params_pr = upload_params.get("pr")

    if not upload_params_branch and not upload_params_pr:
        return repo_default_branch
    elif upload_params_branch and not is_pull_noted_in_branch.match(
        upload_params_branch
    ):
        return upload_params_branch
    else:
        return None


def determine_upload_pr_to_use(upload_params):
    """
    Do processing on the upload request parameters to determine which PR to use for the upload:
    - If a branch was provided and the branch name contains "pull" or "pr" followed by digits, extract the digits and use that as the PR number.
    - Otherwise, use the value provided in the request parameters.
    """
    pullid = is_pull_noted_in_branch.match(upload_params.get("branch") or "")
    if pullid:
        return pullid.groups()[1]
    # The value of pr can be "true" and we use that info when determining upload branch, however we don't want to save that value to the db
    elif upload_params.get("pr") == "true":
        return None
    else:
        return upload_params.get("pr")


def try_to_get_best_possible_bot_token(repository):
    service = repository.author.service
    if repository.bot is not None and repository.bot.oauth_token is not None:
        log.info(
            "Repo has specific bot",
            extra=dict(repoid=repository.repoid, botid=repository.bot.ownerid),
        )
        return encryptor.decrypt_token(repository.bot.oauth_token)
    if (
        repository.author.bot is not None
        and repository.author.bot.oauth_token is not None
    ):
        log.info(
            "Repo Owner has specific bot",
            extra=dict(
                repoid=repository.repoid,
                botid=repository.author.bot.ownerid,
                ownerid=repository.author.ownerid,
            ),
        )
        return encryptor.decrypt_token(repository.author.bot.oauth_token)
    if repository.author.oauth_token is not None:
        log.info(
            "Using repository owner as bot fallback",
            extra=dict(repoid=repository.repoid, ownerid=repository.author.ownerid),
        )
        return encryptor.decrypt_token(repository.author.oauth_token)
    if not repository.private:
        log.info(
            "Using tokenless bot as bot fallback",
            extra=dict(repoid=repository.repoid, ownerid=repository.author.ownerid),
        )
        return get_config(service, "bots", "tokenless")
    return None


@async_to_sync
async def _get_git_commit_data(adapter, commit, token):
    return await adapter.get_commit(commit, token)


def determine_upload_commit_to_use(upload_params, repository):
    """
    Do processing on the upload request parameters to determine which commit to use for the upload:
    - If this is a merge commit on github, use the first commit SHA in the merge commit message.
    - Otherwise, use the value provided in the request parameters.
    """
    # Check if this is a merge commit and, if so, use the commitid of the commit being merged into per the merge commit message.
    # See https://docs.codecov.io/docs/merge-commits for more context.
    service = repository.author.service
    if service.startswith("github") and not upload_params.get(
        "_did_change_merge_commit"
    ):
        token = try_to_get_best_possible_bot_token(repository)
        if token is None:
            return upload_params.get("commit")
        # Get the commit message from the git provider and check if it's structured like a merge commit message
        try:
            adapter = RepoProviderService().get_adapter(
                repository.author, repository, use_ssl=True, token=token
            )
            git_commit_data = _get_git_commit_data(
                adapter, upload_params.get("commit"), token
            )
        except TorngitObjectNotFoundError as e:
            log.warning(
                "Unable to fetch commit. Not found",
                extra=dict(commit=upload_params.get("commit")),
            )
            return upload_params.get("commit")
        except TorngitClientError as e:
            log.warning(
                "Unable to fetch commit", extra=dict(commit=upload_params.get("commit"))
            )
            return upload_params.get("commit")

        git_commit_message = git_commit_data.get("message", "").strip()
        is_merge_commit = re.match(r"^Merge\s\w{40}\sinto\s\w{40}$", git_commit_message)

        if is_merge_commit:
            # If the commit message says "Merge A into B", we'll extract A and use that as the commitid for this upload
            new_commit_id = git_commit_message.split(" ")[1]
            log.info(
                "Upload is for a merge commit, updating commit id for upload",
                extra=dict(
                    commit=upload_params.get("commit"),
                    commit_message=git_commit_message,
                    new_commit=new_commit_id,
                ),
            )
            return new_commit_id

    # If it's not a merge commit we'll just use the commitid provided in the upload parameters
    return upload_params.get("commit")


def insert_commit(commitid, branch, pr, repository, owner, parent_commit_id=None):
    commit, was_created = Commit.objects.defer("_report").get_or_create(
        commitid=commitid,
        repository=repository,
        defaults={
            "branch": branch,
            "pullid": pr,
            "merged": False if pr is not None else None,
            "parent_commit_id": parent_commit_id,
            "state": "pending",
        },
    )

    edited = False
    if commit.state != "pending":
        commit.state = "pending"
        edited = True
    if parent_commit_id and commit.parent_commit_id is None:
        commit.parent_commit_id = parent_commit_id
        edited = True
    if edited:
        commit.save(update_fields=["parent_commit_id", "state"])
    return commit


def get_global_tokens():
    """
    Enterprise only: check the config to see if global tokens were set for this organization's uploads.

    Returns dict with structure {<upload token>: <service name>}
    """
    tokens = {
        get_config(service, "global_upload_token"): service
        for service in global_upload_token_providers
        if get_config(service, "global_upload_token")
    }  # should be empty if we're not in enterprise
    return tokens


def check_commit_upload_constraints(commit: Commit):
    if settings.UPLOAD_THROTTLING_ENABLED and commit.repository.private:
        owner = _determine_responsible_owner(commit.repository)
        limit = USER_PLAN_REPRESENTATIONS.get(owner.plan, {}).monthly_uploads_limit
        if limit is not None:
            did_commit_uploads_start_already = ReportSession.objects.filter(
                report__commit=commit
            ).exists()
            if not did_commit_uploads_start_already:
                limit = USER_PLAN_REPRESENTATIONS[owner.plan].monthly_uploads_limit
                uploads_used = ReportSession.objects.filter(
                    report__commit__repository__author_id=owner.ownerid,
                    report__commit__repository__private=True,
                    created_at__gte=timezone.now() - timedelta(days=30),
                    # attempt at making the query more performant by telling the db to not
                    # check old commits, which are unlikely to have recent uploads
                    report__commit__timestamp__gte=timezone.now() - timedelta(days=60),
                    upload_type="uploaded",
                )[:limit].count()
                if uploads_used >= limit:
                    log.warning(
                        "User exceeded its limits for usage",
                        extra=dict(ownerid=owner.ownerid, repoid=commit.repository_id),
                    )
                    message = "Request was throttled. Throttled due to limit on private repository coverage uploads to Codecov on a free plan. Please upgrade your plan if you require additional uploads this month."
                    raise Throttled(detail=message)


def validate_upload(upload_params, repository, redis):
    """
    Make sure the upload can proceed and, if so, activate the repository if needed.
    """

    validate_activated_repo(repository)
    # Make sure repo hasn't moved
    if not repository.name:
        raise ValidationError(
            "This repository has moved or was deleted. Please login to Codecov to retrieve a new upload token."
        )

    # Check if there are already too many sessions associated with this commit
    try:
        commit = Commit.objects.get(
            commitid=upload_params.get("commit"), repository=repository
        )
        new_session_count = ReportSession.objects.filter(
            ~Q(state="error"),
            ~Q(upload_type=UploadType.CARRIEDFORWARD.db_name),
            report__commit=commit,
        ).count()
        session_count = (commit.totals.get("s") if commit.totals else 0) or 0
        current_upload_limit = get_config("setup", "max_sessions") or 150
        if new_session_count > current_upload_limit:
            if session_count <= current_upload_limit:
                log.info(
                    "Old session count would not have blocked this upload",
                    extra=dict(
                        commit=upload_params.get("commit"),
                        session_count=session_count,
                        repoid=repository.repoid,
                        old_session_count=session_count,
                        new_session_count=new_session_count,
                    ),
                )
            log.warning(
                "Too many uploads to this commit",
                extra=dict(
                    commit=upload_params.get("commit"),
                    session_count=session_count,
                    repoid=repository.repoid,
                ),
            )
            raise ValidationError("Too many uploads to this commit.")
        elif session_count > current_upload_limit:
            log.info(
                "Old session count would block this upload",
                extra=dict(
                    commit=upload_params.get("commit"),
                    session_count=session_count,
                    repoid=repository.repoid,
                    old_session_count=session_count,
                    new_session_count=new_session_count,
                ),
            )
    except Commit.DoesNotExist:
        pass

    # Check if this repository is blacklisted and not allowed to upload
    if redis.sismember("flags.disable_tasks", repository.repoid):
        raise ValidationError(
            "Uploads rejected for this project. Please contact Codecov staff for more details. Sorry for the inconvenience."
        )

    # Make sure the repository author has enough repo credits to upload reports
    if (
        repository.private
        and not repository.activated
        and not bool(get_config("setup", "enterprise_license", default=False))
    ):
        owner = _determine_responsible_owner(repository)

        # If author is on per repo billing, check their repo credits
        if owner.plan not in USER_PLAN_REPRESENTATIONS and owner.repo_credits <= 0:
            raise ValidationError(
                "Sorry, but this team has no private repository credits left."
            )

    if not repository.activated:
        SegmentService().account_activated_repository_on_upload(
            repository.author.ownerid, repository
        )

    # Activate the repository
    repository.activated = True
    repository.active = True
    repository.deleted = False
    repository.save(update_fields=["activated", "active", "deleted", "updatestamp"])


def _determine_responsible_owner(repository):
    owner = repository.author

    if owner.service == "gitlab":
        # Gitlab authors have a "subgroup" structure, so find the parent group before checking repo credits
        while owner.parent_service_id is not None:
            owner = Owner.objects.get(
                service_id=owner.parent_service_id, service=owner.service
            )
    return owner


def parse_headers(headers, upload_params):
    version = upload_params.get("version")

    # Content disposition header
    if headers.get("Content_Disposition") not in (None, "inline"):
        raise ValidationError("Setting Content-Disposition is not supported")

    # Content type
    if version == "v2":
        content_type = "application/x-gzip"
        reduced_redundancy = False
    else:
        content_type = (
            "text/plain"
            if headers.get("X_Content_Type") in (None, "text/html")
            else headers.get("X_Content_Type")
        )
        reduced_redundancy = (
            False
            if "node" in upload_params.get("package", "")
            else headers.get("X_Reduced_Redundancy") in ("true", None)
        )

    if content_type not in ("text/plain", "application/x-gzip", "plain/text"):
        # Prevent customers from setting headers that could result in a XSS attack
        content_type = "text/plain"

    return {"content_type": content_type, "reduced_redundancy": reduced_redundancy}


def store_report_in_redis(request, commitid, reportid, redis):
    encoding = request.META.get("HTTP_X_CONTENT_ENCODING") or request.META.get(
        "HTTP_CONTENT_ENCODING"
    )
    redis_key = (
        f"upload/{commitid[:7]}/{reportid}/{'gzip' if encoding == 'gzip' else 'plain'}"
    )
    redis.setex(redis_key, 10800, request.body)

    return redis_key


def dispatch_upload_task(task_arguments, repository, redis):
    # Store task arguments in redis
    cache_uploads_eta = get_config(("setup", "cache", "uploads"), default=86400)
    repo_queue_key = f"uploads/{repository.repoid}/{task_arguments.get('commit')}"
    countdown = 4 if task_arguments.get("version") == "v4" else 0

    redis.rpush(repo_queue_key, dumps(task_arguments))
    redis.expire(
        repo_queue_key, cache_uploads_eta if cache_uploads_eta is not True else 86400
    )
    redis.setex(
        f"latest_upload/{repository.repoid}/{task_arguments.get('commit')}",
        3600,
        timezone.now().timestamp(),
    )

    # Send task to worker
    TaskService().upload(
        repoid=repository.repoid,
        commitid=task_arguments.get("commit"),
        report_code=task_arguments.get("report_code"),
        countdown=max(
            countdown, int(get_config("setup", "upload_processing_delay") or 0)
        ),
    )


def validate_activated_repo(repository):
    if repository.active and not repository.activated:
        settings_url = f"{settings.CODECOV_DASHBOARD_URL}/{repository.author.service}/{repository.author.username}/{repository.name}/settings"
        raise ValidationError(
            f"This repository has been deactivated. To resume uploading to it, please activate the repository in the codecov UI: {settings_url}"
        )
