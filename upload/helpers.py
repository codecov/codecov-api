import logging
import re
from json import dumps
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import jwt
from asgiref.sync import async_to_sync
from cerberus import Validator
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.http import HttpRequest
from django.utils import timezone
from jwt import PyJWKClient, PyJWTError
from redis import Redis
from rest_framework.exceptions import NotFound, Throttled, ValidationError
from shared.github import InvalidInstallationError
from shared.plan.service import PlanService
from shared.reports.enums import UploadType
from shared.torngit.base import TorngitBaseAdapter
from shared.torngit.exceptions import TorngitClientError, TorngitObjectNotFoundError
from shared.typings.oauth_token_types import OauthConsumerToken
from shared.upload.utils import query_monthly_coverage_measurements

from codecov_auth.models import (
    GITHUB_APP_INSTALLATION_DEFAULT_NAME,
    SERVICE_GITHUB,
    SERVICE_GITHUB_ENTERPRISE,
    GithubAppInstallation,
    Owner,
    Plan,
)
from core.models import Commit, Repository
from reports.models import CommitReport, ReportSession
from services.analytics import AnalyticsService
from services.redis_configuration import get_redis_connection
from services.repo_providers import RepoProviderService
from services.task import TaskService
from upload.tokenless.tokenless import TokenlessUploadHandler
from utils import is_uuid
from utils.config import get_config
from utils.encryption import encryptor
from utils.github import get_github_integration_token

from .constants import ci, global_upload_token_providers

is_pull_noted_in_branch = re.compile(r".*(pull|pr)\/(\d+).*")

# Valid values are `https://dev.azure.com/username/` or `https://username.visualstudio.com/`
# May be URL-encoded, so ':' can be '%3A' and '/' can be '%2F'
# Username is alphanumeric with '_' and '-'
_valid_azure_server_uri = r"^https?(?:://|%3A%2F%2F)(?:dev.azure.com(?:/|%2F)[a-zA-Z0-9_-]+(?:/|%2F)|[a-zA-Z0-9_-]+.visualstudio.com(?:/|%2F))$"

log = logging.getLogger(__name__)
redis = get_redis_connection()


def parse_params(data: Dict[str, Any]) -> Dict[str, Any]:
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
                lambda document: (
                    document.get("slug")
                    .rsplit("/", 1)[0]
                    .replace(
                        "/", ":"
                    )  # we use ':' as separator for gitlab subgroups internally
                    if document.get("slug")
                    and len(document.get("slug").rsplit("/", 1)) == 2
                    else None
                )
            ),
        },
        # repo name, we set this by parsing the value of "slug" if provided
        "repo": {
            "type": "string",
            "nullable": True,
            "default_setter": (
                lambda document: (
                    document.get("slug").rsplit("/", 1)[1]
                    if document.get("slug")
                    and len(document.get("slug").rsplit("/", 1)) == 2
                    else None
                )
            ),
        },
        # indicates whether the token provided is a global upload token rather than a repository upload token
        # note: this needs to go before the "service" field in the schema so we can use is when determining the service value to use
        "using_global_token": {
            "type": "boolean",
            "default_setter": (
                lambda document: (
                    True
                    if document.get("token") and document.get("token") in global_tokens
                    else False
                )
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
                {"regex": r"^[0-9a-f]{8}(-?[0-9a-f]{4}){3}-?[0-9a-f]{12}$"},  # UUID
                {"regex": r"(^[A-Za-z0-9-_]*\.[A-Za-z0-9-_]*\.[A-Za-z0-9-_]*$)"},  # JWT
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
                lambda document: (
                    global_tokens[document.get("token")]
                    if document.get("using_global_token")
                    else None
                )
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
                lambda value: (
                    None if value in ["false", "null", "undefined", "true"] else value
                )
            ),
        },
        "build_url": {"type": "string", "regex": r"^https?\:\/\/(.{,200})"},
        "flags": {"type": "string", "regex": r"^[\w\.\-\,]+$"},
        "branch": {
            "type": "string",
            "nullable": True,
            "coerce": (
                lambda value: (
                    None
                    if value == "HEAD"
                    # if prefixed with "origin/" or "refs/heads", the prefix will be removed
                    else (
                        value[7:]
                        if value[:7] == "origin/"
                        else value[11:]
                        if value[:11] == "refs/heads/"
                        else value
                    )
                ),
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
                lambda value: (
                    None if value in ["null", "undefined", "none", "nil"] else value
                )
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
        "project": {"type": "string"},
        "server_uri": {
            "type": "string",
            "regex": _valid_azure_server_uri,
        },
        "root": {"type": "string"},  # deprecated
        "storage_path": {"type": "string"},
    }

    v = Validator(params_schema, allow_unknown=True)
    if not v.validate(non_empty_data):
        raise ValidationError(v.errors)
    # override service to the one from the global token if global token is in use
    if v.document.get("using_global_token"):
        v.document["service"] = global_tokens[v.document.get("token")]
    # return validated data, including coerced values
    return v.document


def get_repo_with_github_actions_oidc_token(token: str) -> Repository:
    unverified_contents = jwt.decode(token, options={"verify_signature": False})
    token_issuer = str(unverified_contents.get("iss"))
    parsed_url = urlparse(token_issuer)
    if parsed_url.hostname == "token.actions.githubusercontent.com":
        service = "github"
        jwks_url = "https://token.actions.githubusercontent.com/.well-known/jwks"
    else:
        service = "github_enterprise"
        github_enterprise_url = get_config("github_enterprise", "url")
        if not github_enterprise_url:
            raise ValidationError("GitHub Enterprise URL configuration is not set")
        # remove trailing slashes if present
        github_enterprise_url = re.sub(r"/+$", "", github_enterprise_url)
        jwks_url = f"{github_enterprise_url}/_services/token/.well-known/jwks"
    jwks_client = PyJWKClient(jwks_url)
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    data = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=[settings.CODECOV_API_URL, settings.CODECOV_URL],
    )
    repo = str(data.get("repository")).split("/")[-1]
    repository = Repository.objects.get(
        author__service=service,
        name=repo,
        author__username=data.get("repository_owner"),
    )
    return repository


def determine_repo_for_upload(upload_params: Dict[str, Any]) -> Repository:
    token = upload_params.get("token")
    using_global_token = upload_params.get("using_global_token")
    service = upload_params.get("service")

    if token and not using_global_token:
        if is_uuid(token):
            try:
                repository = Repository.objects.get(upload_token=token)
            except ObjectDoesNotExist:
                raise NotFound(
                    f"Could not find a repository associated with upload token {token}"
                )
        elif service == "github-actions":
            try:
                repository = get_repo_with_github_actions_oidc_token(token)
            except PyJWTError:
                raise ValidationError(
                    "Could not validate upload request using Github token"
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
            raise NotFound("Could not find a repository, try using repo upload token")
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


def determine_upload_branch_to_use(
    upload_params: Dict[str, Any], repo_default_branch: str
) -> str | None:
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


def determine_upload_pr_to_use(upload_params: Dict[str, Any]) -> str | None:
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


def ghapp_installation_id_to_use(repository: Repository) -> Optional[str]:
    if (
        repository.service != SERVICE_GITHUB
        and repository.service != SERVICE_GITHUB_ENTERPRISE
    ):
        return None

    gh_app_default_installation: GithubAppInstallation = (
        repository.author.github_app_installations.filter(
            name=GITHUB_APP_INSTALLATION_DEFAULT_NAME
        ).first()
    )
    if (
        gh_app_default_installation
        and gh_app_default_installation.is_repo_covered_by_integration(repository)
    ):
        return gh_app_default_installation.installation_id
    elif repository.using_integration and repository.author.integration_id:
        # THIS FLOW IS DEPRECATED
        # it will (hopefully) be removed after the ghapp installation work is complete
        # and the data is backfilles appropriately
        return repository.author.integration_id


def try_to_get_best_possible_bot_token(
    repository: Repository,
) -> OauthConsumerToken | Dict:
    ghapp_installation_id = ghapp_installation_id_to_use(repository)
    if ghapp_installation_id is not None:
        try:
            github_token = get_github_integration_token(
                repository.author.service,
                installation_id=ghapp_installation_id,
            )
            return dict(key=github_token)
        except InvalidInstallationError:
            log.warning(
                "Invalid installation error",
                extra=dict(
                    service=repository.author.service,
                    integration_id=ghapp_installation_id,
                ),
            )
            # now we'll fallback to trying an OAuth token
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
async def _get_git_commit_data(
    adapter: TorngitBaseAdapter, commit: str, token: Optional[OauthConsumerToken | Dict]
) -> Dict[str, Any]:
    return await adapter.get_commit(commit, token)


def determine_upload_commit_to_use(
    upload_params: Dict[str, Any], repository: Repository
) -> str:
    """
    Do processing on the upload request parameters to determine which commit to use for the upload:
    - If this is a merge commit on github, use the first commit SHA in the merge commit message.
    - Otherwise, use the value provided in the request parameters.
    """
    # Check if this is a merge commit and, if so, use the commitid of the commit being merged into per the merge commit message.
    # See https://docs.codecov.io/docs/merge-commits for more context.
    service = repository.author.service
    commitid = upload_params.get("commit", "")
    if service.startswith("github") and not upload_params.get(
        "_did_change_merge_commit"
    ):
        token = try_to_get_best_possible_bot_token(repository)
        if token is None:
            return commitid
        # Get the commit message from the git provider and check if it's structured like a merge commit message
        try:
            adapter = RepoProviderService().get_adapter(
                repository.author, repository, use_ssl=True, token=token
            )
            git_commit_data = _get_git_commit_data(adapter, commitid, token)
        except TorngitObjectNotFoundError:
            log.warning(
                "Unable to fetch commit. Not found",
                extra=dict(commit=commitid),
            )
            return commitid
        except TorngitClientError:
            log.warning("Unable to fetch commit", extra=dict(commit=commitid))
            return commitid

        git_commit_message = git_commit_data.get("message", "").strip()
        is_merge_commit = re.match(r"^Merge\s\w{40}\sinto\s\w{40}$", git_commit_message)

        if is_merge_commit:
            # If the commit message says "Merge A into B", we'll extract A and use that as the commitid for this upload
            new_commit_id = git_commit_message.split(" ")[1]
            log.info(
                "Upload is for a merge commit, updating commit id for upload",
                extra=dict(
                    commit=commitid,
                    commit_message=git_commit_message,
                    new_commit=new_commit_id,
                ),
            )
            return new_commit_id

    # If it's not a merge commit we'll just use the commitid provided in the upload parameters
    return commitid


def insert_commit(
    commitid: str,
    branch: str,
    pr: int,
    repository: Repository,
    owner: Owner,
    parent_commit_id: Optional[str] = None,
) -> Commit:
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
    if parent_commit_id and commit.parent_commit_id is None:
        commit.parent_commit_id = parent_commit_id
        edited = True
    if branch and commit.branch != branch:
        # A branch head may have been moved; this allows commits to be "moved"
        commit.branch = branch
        edited = True
    if edited:
        commit.save(update_fields=["parent_commit_id", "branch"])
    return commit


def get_global_tokens() -> Dict[str | None, Any]:
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


def check_commit_upload_constraints(commit: Commit) -> None:
    if settings.UPLOAD_THROTTLING_ENABLED and commit.repository.private:
        owner = _determine_responsible_owner(commit.repository)
        plan_service = PlanService(current_org=owner)
        limit = plan_service.monthly_uploads_limit
        if limit is not None:
            did_commit_uploads_start_already = ReportSession.objects.filter(
                report__commit=commit
            ).exists()
            if not did_commit_uploads_start_already:
                if (
                    query_monthly_coverage_measurements(plan_service=plan_service)
                    >= limit
                ):
                    log.warning(
                        "User exceeded its limits for usage",
                        extra=dict(ownerid=owner.ownerid, repoid=commit.repository_id),
                    )
                    message = "Request was throttled. Throttled due to limit on private repository coverage uploads to Codecov on a free plan. Please upgrade your plan if you require additional uploads this month."
                    raise Throttled(detail=message)


def validate_upload(
    upload_params: Dict[str, Any], repository: Repository, redis: Redis
) -> None:
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
        if (
            owner.plan not in Plan.objects.values_list("name", flat=True)
            and owner.repo_credits <= 0
        ):
            raise ValidationError(
                "Sorry, but this team has no private repository credits left."
            )

    if not repository.activated:
        AnalyticsService().account_activated_repository_on_upload(
            repository.author.ownerid, repository
        )

    if (
        not repository.activated
        or not repository.active
        or repository.deleted
        or not repository.coverage_enabled
    ):
        # Activate the repository
        repository.activated = True
        repository.active = True
        repository.deleted = False
        repository.coverage_enabled = True
        repository.save(
            update_fields=["activated", "active", "deleted", "coverage_enabled"]
        )


def _determine_responsible_owner(repository: Repository) -> Owner:
    owner = repository.author

    if owner.service == "gitlab":
        # Gitlab authors have a "subgroup" structure, so find the parent group before checking repo credits
        while owner.parent_service_id is not None:
            owner = Owner.objects.get(
                service_id=owner.parent_service_id, service=owner.service
            )
    return owner


def parse_headers(
    headers: Dict[str, Any], upload_params: Dict[str, Any]
) -> Dict[str, Any]:
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
            if headers.get("X_Content_Type", "") in ("", "text/html")
            else headers.get("X_Content_Type", "")
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


def dispatch_upload_task(
    task_arguments: Dict[str, Any],
    repository: Repository,
    redis: Redis,
    report_type: Optional[CommitReport.ReportType] = CommitReport.ReportType.COVERAGE,
) -> None:
    # Store task arguments in redis
    cache_uploads_eta = get_config(("setup", "cache", "uploads"), default=86400)
    if report_type == CommitReport.ReportType.COVERAGE:
        repo_queue_key = f"uploads/{repository.repoid}/{task_arguments.get('commit')}"
    else:
        repo_queue_key = (
            f"uploads/{repository.repoid}/{task_arguments.get('commit')}/{report_type}"
        )

    countdown = 0
    if task_arguments.get("version") == "v4":
        countdown = 4
    if (
        report_type == CommitReport.ReportType.BUNDLE_ANALYSIS
        or CommitReport.ReportType.TEST_RESULTS
    ):
        countdown = 4

    redis.rpush(repo_queue_key, dumps(task_arguments))
    redis.expire(
        repo_queue_key, cache_uploads_eta if cache_uploads_eta is not True else 86400
    )

    if report_type == CommitReport.ReportType.COVERAGE:
        latest_upload_key = (
            f"latest_upload/{repository.repoid}/{task_arguments.get('commit')}"
        )
    else:
        latest_upload_key = f"latest_upload/{repository.repoid}/{task_arguments.get('commit')}/{report_type}"
    redis.setex(
        latest_upload_key,
        3600,
        timezone.now().timestamp(),
    )
    commitid = task_arguments.get("commit")

    TaskService().upload(
        repoid=repository.repoid,
        commitid=commitid,
        report_type=str(report_type),
        report_code=task_arguments.get("report_code"),
        arguments=task_arguments,
        countdown=max(
            countdown, int(get_config("setup", "upload_processing_delay") or 0)
        ),
    )


def validate_activated_repo(repository: Repository) -> None:
    if repository.active and not repository.activated:
        config_url = f"{settings.CODECOV_DASHBOARD_URL}/{repository.author.service}/{repository.author.username}/{repository.name}/config/general"
        raise ValidationError(
            f"This repository is deactivated. To resume uploading to it, please activate the repository in the codecov UI: {config_url}"
        )


# headers["User-Agent"] should look something like this: codecov-cli/0.4.7 or codecov-uploader/0.7.1
def get_agent_from_headers(headers: Dict[str, Any]) -> str:
    try:
        return headers["User-Agent"].split("/")[0].split("-")[1]
    except Exception as e:
        log.warning(
            "Error getting agent from user agent header",
            extra=dict(
                err=str(e),
            ),
        )
        return "unknown-user-agent"


def get_version_from_headers(headers: Dict[str, Any]) -> str:
    try:
        return headers["User-Agent"].split("/")[1]
    except Exception as e:
        log.warning(
            "Error getting version from user agent header",
            extra=dict(
                err=str(e),
            ),
        )
        return "unknown-user-agent"


def generate_upload_prometheus_metrics_labels(
    action: str,
    request: HttpRequest,
    is_shelter_request: bool,
    endpoint: Optional[str] = None,
    repository: Optional[Repository] = None,
    position: Optional[str] = None,
    upload_version: Optional[str] = None,
    include_empty_labels: bool = True,
) -> Dict[str, Any]:
    metrics_tags = dict(
        agent=get_agent_from_headers(request.headers),
        version=get_version_from_headers(request.headers),
        action=action,
        endpoint=endpoint,
        is_using_shelter="yes" if is_shelter_request else "no",
    )

    repo_visibility = None
    if repository:
        repo_visibility = "private" if repository.private else "public"

    optional_fields = {
        "repo_visibility": repo_visibility,
        "position": position,
        "upload_version": upload_version,
    }

    metrics_tags.update(
        {
            field: value
            for field, value in optional_fields.items()
            if value or include_empty_labels
        }
    )

    return metrics_tags
