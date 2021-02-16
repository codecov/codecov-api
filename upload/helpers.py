import re
import asyncio
import logging
from cerberus import Validator
from json import dumps
from rest_framework.exceptions import ValidationError, NotFound
from django.core.exceptions import ObjectDoesNotExist
from core.models import Repository, Commit
from codecov_auth.models import Owner
from utils.config import get_config
from .constants import ci, global_upload_token_providers
from services.repo_providers import RepoProviderService
from services.task import TaskService
from services.segment import SegmentService
from codecov_auth.constants import USER_PLAN_REPRESENTATIONS
from shared.torngit.exceptions import TorngitObjectNotFoundError, TorngitClientError

from upload.tokenless.tokenless import TokenlessUploadHandler

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
        "build_url": {"type": "string", "regex": r"^https?\:\/\/(.{,100})",},
        "flags": {"type": "string", "regex": r"^[\w\.\-\,]+$",},
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
        "package": {"type": "string"},
        "s3": {"type": "integer"},
        "yaml": {
            "type": "string"
        },  # file path to custom location of codecov.yml in repo
        "url": {"type": "string"},  # custom location where report is found
        "parent": {"type": "string"},
        "package": {"type": "string"},
        "project": {"type": "string"},
        "server_uri": {"type": "string"},
        "root": {"type": "string",},  # deprecated
    }

    v = Validator(params_schema, allow_unknown=True)
    if not v.validate(non_empty_data):
        raise ValidationError(v.errors)

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
        git_service = TokenlessUploadHandler(service, upload_params).verify_upload()
        try: 
            repository = Repository.objects.get(author__service=git_service, name=upload_params.get("repo"), author__username=upload_params.get("owner"))
        except ObjectDoesNotExist:
            raise NotFound(
                f"Could not find a repository, try using upload token"
            )
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
    pullid = is_pull_noted_in_branch.match(upload_params.get("branch", ""))
    if pullid:
        return pullid.groups()[1]
    else:
        return upload_params.get("pr")


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
        token = (
            repository.bot.oauth_token
            if repository.bot and repository.bot.oauth_token
            else get_config(service, "bot")
        )

        # Get the commit message from the git provider and check if it's structured like a merge commit message
        try:
            git_commit_data = asyncio.run(
                RepoProviderService()
                .get_adapter(repository.author, repository, use_ssl=True, token=token)
                .get_commit(upload_params.get("commit"), token)
            )
        except TorngitObjectNotFoundError as e:
            log.error(
                "Unable to fetch commit. Not found",
                extra=dict(
                    commit=upload_params.get("commit"),
                ),
            )
            return upload_params.get("commit")
        except TorngitClientError as e:
            log.error(
                "Unable to fetch commit",
                extra=dict(
                    commit=upload_params.get("commit"),
                ),
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
    
    try:
        commit = Commit.objects.get(
            commitid=commitid, repository=repository
        )
        edited = False

        if commit.state != "pending":
           commit.state = "pending"
           edited = True

        if parent_commit_id and commit.parent_commit_id is None:
           commit.parent_commit_id = parent_commit_id
           edited = True

        if edited:
           commit.save()
            
    except Commit.DoesNotExist:
        log.info("Creating new commit for upload",                 
            extra=dict(
            commit=commitid,
            branch=branch,
            repository=repository,
            owner=owner
        ),)
        commit = Commit(
            commitid=commitid, repository=repository, state="pending"
        )
        commit.branch = branch
        commit.pullid = pr
        commit.merged = False if pr is not None else None
        commit.parent_commit_id = parent_commit_id
        commit.save()


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


def validate_upload(upload_params, repository, redis):
    """
    Make sure the upload can proceed and, if so, activate the repository if needed.
    """

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
        session_count = commit.totals.get("s", 0) if commit.totals else 0
        if (session_count or 0) > (get_config("setup", "max_sessions") or 30):
            raise ValidationError("Too many uploads to this commit.")
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

        owner = repository.author

        if owner.service == "gitlab":
            # Gitlab authors have a "subgroup" structure, so find the parent group before checking repo credits
            while owner.parent_service_id is not None:
                owner = Owner.objects.get(service_id=owner.parent_service_id, service=owner.service)

        # If author is on per repo billing, check their repo credits
        if owner.plan not in USER_PLAN_REPRESENTATIONS and owner.repo_credits <= 0:
            raise ValidationError(
                "Sorry, but this team has no private repository credits left."
            )

    # Activate the repository
    repository.activated = True
    repository.active = True
    repository.deleted = False
    repository.save()

    SegmentService().account_activated_repository_on_upload(repository.author.ownerid, repository)


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
    if not request.META.get("X_REDIS_KEY"):
        encoding = request.META.get("HTTP_X_CONTENT_ENCODING") or request.META.get(
            "HTTP_CONTENT_ENCODING"
        )
        redis_key = f"upload/{commitid[:7]}/{reportid}/{'gzip' if encoding == 'gzip' else 'plain'}"
    else:
        redis_key = request.META.get("X_REDIS_KEY")
    redis.setex(redis_key, 10800, request.body)

    return redis_key


def dispatch_upload_task(task_arguments, repository, redis):
    # Store task arguments in redis
    cache_uploads_eta = get_config(("setup", "cache", "uploads"), default=86400)
    repo_queue_key = f"uploads/{repository.repoid}/{task_arguments.get('commit')}"
    countdown = 4 if task_arguments.get("version") == "v4" else 0

    redis.rpush(repo_queue_key, dumps(task_arguments))
    redis.expire(
        repo_queue_key, cache_uploads_eta if cache_uploads_eta is not True else 86400,
    )

    # Send task to worker
    TaskService().upload(
        repoid=repository.repoid,
        commitid=task_arguments.get("commit"),
        countdown=countdown,
    )
