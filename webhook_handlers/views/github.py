import hmac
import logging
import re
from contextlib import suppress
from hashlib import sha1

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from codecov_auth.models import Owner
from core.models import Branch, Commit, Pull, Repository
from services.archive import ArchiveService
from services.billing import BillingService
from services.redis_configuration import get_redis_connection
from services.segment import BLANK_SEGMENT_USER_ID, SegmentService
from services.task import TaskService
from utils.config import get_config
from webhook_handlers.constants import (
    GitHubHTTPHeaders,
    GitHubWebhookEvents,
    WebhookHandlerErrorMessages,
)

log = logging.getLogger(__name__)


# This should probably go somewhere where it can be easily shared
regexp_ci_skip = re.compile(r"\[(ci|skip| |-){3,}\]").search


class GithubWebhookHandler(APIView):
    """
    GitHub Webhook Handler. Method names correspond to events as defined in

        webhook_handlers.constants.GitHubWebhookEvents
    """

    permission_classes = [AllowAny]
    redis = get_redis_connection()

    segment_service = SegmentService()

    def validate_signature(self, request):
        key = get_config(
            "github", "webhook_secret", default=b"testixik8qdauiab1yiffydimvi72ekq"
        )
        if type(key) is str:
            # If "key" comes from k8s secret, it is of type str, so
            # must convert to bytearray for use with hmac
            key = bytes(key, "utf-8")

        sig = "sha1=" + hmac.new(key, request.body, digestmod=sha1).hexdigest()

        if sig != request.META.get(GitHubHTTPHeaders.SIGNATURE):
            raise PermissionDenied()

    def unhandled_webhook_event(self, request, *args, **kwargs):
        return Response(data=WebhookHandlerErrorMessages.UNSUPPORTED_EVENT)

    def _get_repo(self, request):
        """
        Attempts to fetch the repo first via the index on o(wnerid, service_id),
        then naively on service, service_id if that fails.
        """
        repo_data = self.request.data.get("repository", {})
        repo_service_id = repo_data.get("id")
        owner_service_id = repo_data.get("owner", {}).get("id")
        repo_slug = repo_data.get("full_name")

        try:
            owner = Owner.objects.get(service="github", service_id=owner_service_id)
        except Owner.DoesNotExist:
            log.info(
                f"Error fetching owner with service_id {owner_service_id}, "
                f"using repository service id to get repo",
                extra=dict(repo_service_id=repo_service_id, repo_slug=repo_slug),
            )
            try:
                log.info(
                    "Unable to find repository owner, fetching repo with service, service_id",
                    extra=dict(repo_service_id=repo_service_id, repo_slug=repo_slug),
                )
                return Repository.objects.get(
                    author__service="github", service_id=repo_service_id
                )
            except Repository.DoesNotExist:
                log.info(
                    f"Received event for non-existent repository",
                    extra=dict(repo_service_id=repo_service_id, repo_slug=repo_slug),
                )
                raise NotFound("Repository does not exist")
        else:
            try:
                log.info(
                    "Found repository owner, fetching repo with ownerid, service_id",
                    extra=dict(repo_service_id=repo_service_id, repo_slug=repo_slug),
                )
                return Repository.objects.get(
                    author__ownerid=owner.ownerid, service_id=repo_service_id
                )
            except Repository.DoesNotExist:
                if owner.integration_id:
                    log.info(
                        "Repository no found but owner is using integration, creating repository"
                    )
                    return Repository.objects.get_or_create_from_git_repo(
                        repo_data, owner
                    )[0]
                log.info(
                    f"Received event for non-existent repository",
                    extra=dict(repo_service_id=repo_service_id, repo_slug=repo_slug),
                )
                raise NotFound("Repository does not exist")

    def ping(self, request, *args, **kwargs):
        return Response(data="pong")

    def repository(self, request, *args, **kwargs):
        action, repo = self.request.data.get("action"), self._get_repo(request)
        if action == "publicized":
            repo.private, repo.activated = False, False
            repo.save()
            log.info(
                "Repository publicized",
                extra=dict(repoid=repo.repoid, github_webhook_event=self.event),
            )
        elif action == "privatized":
            repo.private = True
            repo.save()
            log.info(
                "Repository privatized",
                extra=dict(repoid=repo.repoid, github_webhook_event=self.event),
            )
        elif action == "deleted":
            log.info(f"Request to delete repository: {repo.repoid}")
            repo.deleted = True
            repo.activated = False
            repo.active = False
            repo.save(update_fields=["deleted", "activated", "active"])
            log.info(
                "Repository soft-deleted",
                extra=dict(repoid=repo.repoid, github_webhook_event=self.event),
            )
        else:
            log.warning(
                f"Unknown repository action: {action}", extra=dict(repoid=repo.repoid)
            )
        return Response()

    def delete(self, request, *args, **kwargs):
        ref_type = request.data.get("ref_type")
        repo = self._get_repo(request)
        if ref_type != "branch":
            log.info(
                f"Unsupported ref type: {ref_type}, exiting",
                extra=dict(repoid=repo.repoid, github_webhook_event=self.event),
            )
            return Response(f"Unsupported ref type: {ref_type}")
        branch_name = self.request.data.get("ref")[11:]
        Branch.objects.filter(
            repository=self._get_repo(request), name=branch_name
        ).delete()
        log.info(
            f"Branch '{branch_name}' deleted",
            extra=dict(repoid=repo.repoid, github_webhook_event=self.event),
        )
        return Response()

    def public(self, request, *args, **kwargs):
        repo = self._get_repo(request)
        repo.private, repo.activated = False, False
        repo.save()
        log.info(
            "Repository publicized",
            extra=dict(repoid=repo.repoid, github_webhook_event=self.event),
        )
        return Response()

    def push(self, request, *args, **kwargs):
        ref_type = "branch" if request.data.get("ref")[5:10] == "heads" else "tag"
        repo = self._get_repo(request)
        if ref_type != "branch":
            log.info(
                "Ref is tag, not branch, ignoring push event",
                extra=dict(repoid=repo.repoid, github_webhook_event=self.event),
            )
            return Response(f"Unsupported ref type: {ref_type}")

        if not repo.active:
            log.info(
                "Repository is not active, ignoring push event",
                extra=dict(repoid=repo.repoid, github_webhook_event=self.event),
            )
            return Response(data=WebhookHandlerErrorMessages.SKIP_NOT_ACTIVE)

        branch_name = self.request.data.get("ref")[11:]
        commits = self.request.data.get("commits", [])

        if not commits:
            log.info(
                f"No commits in webhook payload for branch {branch_name}",
                extra=dict(repoid=repo.repoid, github_webhook_event=self.event),
            )
            return Response()

        commits_queryset = Commit.objects.filter(
            repository=repo,
            commitid__in=[commit.get("id") for commit in commits],
            merged=False,
        )
        commits_queryset.update(branch=branch_name)
        if branch_name == repo.branch:
            commits_queryset.update(merged=True)
            log.info(
                "Pushed commits to default branch; setting merged to True",
                extra=dict(
                    repoid=repo.repoid,
                    github_webhook_event=self.event,
                    commits=[commit.get("id") for commit in commits],
                ),
            )

        log.info(
            f"Branch name updated for commits to {branch_name}",
            extra=dict(repoid=repo.repoid, github_webhook_event=self.event),
        )

        most_recent_commit = commits[-1]

        if regexp_ci_skip(most_recent_commit.get("message")):
            log.info(
                "CI skip tag on head commit, not setting status",
                extra=dict(
                    repoid=repo.repoid,
                    commit=most_recent_commit.get("id"),
                    github_webhook_event=self.event,
                ),
            )
            return Response(data="CI Skipped")

        if self.redis.sismember("beta.pending", repo.repoid):
            log.info(
                "Triggering status set pending task",
                extra=dict(
                    repoid=repo.repoid,
                    commit=most_recent_commit.get("id"),
                    github_webhook_event=self.event,
                ),
            )
            TaskService().status_set_pending(
                repoid=repo.repoid,
                commitid=most_recent_commit.get("id"),
                branch=branch_name,
                on_a_pull_request=False,
            )

        return Response()

    def status(self, request, *args, **kwargs):
        repo = self._get_repo(request)
        commitid = request.data.get("sha")

        if not repo.active:
            log.info(
                "Repository is not active, ignoring status event",
                extra=dict(
                    repoid=repo.repoid, commit=commitid, github_webhook_event=self.event
                ),
            )
            return Response(data=WebhookHandlerErrorMessages.SKIP_NOT_ACTIVE)
        if request.data.get("context", "")[:8] == "codecov/":
            log.info(
                "Status is Codecov status, exiting",
                extra=dict(
                    repoid=repo.repoid, commit=commitid, github_webhook_event=self.event
                ),
            )
            return Response(data=WebhookHandlerErrorMessages.SKIP_CODECOV_STATUS)
        if request.data.get("state") == "pending":
            log.info(
                "Commit in pending state, exiting",
                extra=dict(
                    repoid=repo.repoid, commit=commitid, github_webhook_event=self.event
                ),
            )
            return Response(data=WebhookHandlerErrorMessages.SKIP_PENDING_STATUSES)

        if not Commit.objects.filter(
            repository=repo, commitid=commitid, state="complete"
        ).exists():
            return Response(data=WebhookHandlerErrorMessages.SKIP_PROCESSING)

        log.info(
            "Triggering notify task",
            extra=dict(
                repoid=repo.repoid, commit=commitid, github_webhook_event=self.event
            ),
        )

        TaskService().notify(repoid=repo.repoid, commitid=commitid)

        return Response()

    def pull_request(self, request, *args, **kwargs):
        repo = self._get_repo(request)

        if not repo.active:
            log.info(
                "Repository is not active, ignoring pull request event",
                extra=dict(repoid=repo.repoid, github_webhook_event=self.event),
            )
            return Response(data=WebhookHandlerErrorMessages.SKIP_NOT_ACTIVE)

        action, pullid = request.data.get("action"), request.data.get("number")

        if action in ["opened", "closed", "reopened", "synchronize"]:
            log.info(
                f"Pull request action is '{action}', triggering pulls_sync task",
                extra=dict(
                    repoid=repo.repoid, github_webhook_event=self.event, pullid=pullid
                ),
            )
            TaskService().pulls_sync(repoid=repo.repoid, pullid=pullid)
        elif action == "edited":
            log.info(
                f"Pull request action is 'edited', updating pull title to "
                f"'{request.data.get('pull_request', {}).get('title')}'",
                extra=dict(
                    repoid=repo.repoid, github_webhook_event=self.event, pullid=pullid
                ),
            )
            Pull.objects.filter(repository=repo, pullid=pullid).update(
                title=request.data.get("pull_request", {}).get("title")
            )

        return Response()

    def _handle_installation_events(self, request, *args, **kwargs):
        service_id = request.data["installation"]["account"]["id"]
        username = request.data["installation"]["account"]["login"]
        action = request.data.get("action")

        owner, _ = Owner.objects.get_or_create(
            service="github", service_id=service_id, username=username
        )

        if action == "deleted":
            owner.integration_id = None
            owner.save()
            owner.repository_set.all().update(using_integration=False, bot=None)
            log.info(
                "Owner deleted app integration",
                extra=dict(ownerid=owner.ownerid, github_webhook_event=self.event),
            )
            self.segment_service.account_uninstalled_source_control_service_app(
                owner.ownerid
                if request.data["sender"]["type"] == "User"
                else BLANK_SEGMENT_USER_ID,
                owner.ownerid,
                {"platform": "github"},
            )
        else:
            if owner.integration_id is None:
                owner.integration_id = request.data["installation"]["id"]
                owner.save()

            log.info(
                "Triggering refresh task to sync repos",
                extra=dict(ownerid=owner.ownerid, github_webhook_event=self.event),
            )

            self.segment_service.account_installed_source_control_service_app(
                owner.ownerid
                if request.data["sender"]["type"] == "User"
                else BLANK_SEGMENT_USER_ID,
                owner.ownerid,
                {"platform": "github"},
            )

            TaskService().refresh(
                ownerid=owner.ownerid,
                username=username,
                sync_teams=False,
                sync_repos=True,
                using_integration=True,
            )

        return Response(data="Integration webhook received")

    def installation(self, request, *args, **kwargs):
        return self._handle_installation_events(request, *args, **kwargs)

    def installation_repositories(self, request, *args, **kwargs):
        return self._handle_installation_events(request, *args, **kwargs)

    def organization(self, request, *args, **kwargs):
        action = request.data.get("action")
        if action == "member_removed":
            log.info(
                f"Removing user with service-id {request.data['membership']['user']['id']} "
                f"from organization with service-id {request.data['organization']['id']}",
                extra=dict(github_webhook_event=self.event),
            )

            try:
                org = Owner.objects.get(
                    service="github", service_id=request.data["organization"]["id"]
                )
            except Owner.DoesNotExist:
                log.info("Organization does not exist, exiting")
                return Response(
                    status=status.HTTP_400_BAD_REQUEST,
                    data="Attempted to remove member from non-Codecov org failed",
                )

            try:
                member = Owner.objects.get(
                    service="github",
                    service_id=request.data["membership"]["user"]["id"],
                )
            except Owner.DoesNotExist:
                log.info(
                    f"Member with service-id {request.data['membership']['user']['id']} "
                    f"does not exist, exiting",
                    extra=dict(ownerid=org.ownerid, github_webhook_event=self.event),
                )
                return Response(
                    status=status.HTTP_400_BAD_REQUEST,
                    data="Attempted to remove non Codecov user from Codecov org failed",
                )

            try:
                if member.organizations:
                    member.organizations.remove(org.ownerid)
                    member.save(update_fields=["organizations"])
            except ValueError:
                pass

            try:
                if org.plan_activated_users:
                    org.plan_activated_users.remove(member.ownerid)
                    org.save(update_fields=["plan_activated_users"])
            except ValueError:
                pass

            log.info(
                f"User removal of {member.ownerid}, success",
                extra=dict(ownerid=org.ownerid, github_webhook_event=self.event),
            )

        return Response()

    def _handle_marketplace_events(self, request, *args, **kwargs):
        log.info(
            "Triggering sync_plans task", extra=dict(github_webhook_event=self.event)
        )
        with suppress(Exception):
            # log if users purchase GHM plans while having a stripe plan
            username = request.data["marketplace_purchase"]["account"]["login"]
            owner = Owner.objects.get(service="github", username=username)
            subscription = BillingService(requesting_user=owner).get_subscription(owner)
            if subscription.status == "active":
                log.warning(
                    "GHM webhook - user purchasing but has a Stripe Subscription",
                    extra=dict(username=username),
                )
        TaskService().sync_plans(
            sender=request.data["sender"],
            account=request.data["marketplace_purchase"]["account"],
            action=request.data["action"],
        )
        return Response()

    def marketplace_subscription(self, request, *args, **kwargs):
        return self._handle_marketplace_events(request, *args, **kwargs)

    def marketplace_purchase(self, request, *args, **kwargs):
        return self._handle_marketplace_events(request, *args, **kwargs)

    def member(self, request, *args, **kwargs):
        action = request.data["action"]
        if action == "removed":
            repo = self._get_repo(request)
            log.info(
                f"Request to remove read permissions for user",
                extra=dict(repoid=repo.repoid, github_webhook_event=self.event),
            )
            try:
                member = Owner.objects.get(
                    service="github", service_id=request.data["member"]["id"]
                )
            except Owner.DoesNotExist:
                log.info(
                    f"Repository permissions unchanged -- owner doesn't exist",
                    extra=dict(repoid=repo.repoid, github_webhook_event=self.event),
                )
                return Response(status=status.HTTP_404_NOT_FOUND)

            try:
                member.permission.remove(repo.repoid)
                member.save(update_fields=["permission"])
                log.info(
                    "Successfully updated read permissions for repository",
                    extra=dict(
                        repoid=repo.repoid,
                        ownerid=member.ownerid,
                        github_webhook_event=self.event,
                    ),
                )
            except (ValueError, AttributeError):
                log.info(
                    f"Member didn't have read permissions, didn't update",
                    extra=dict(
                        repoid=repo.repoid,
                        ownerid=member.ownerid,
                        github_webhook_event=self.event,
                    ),
                )

        return Response()

    def post(self, request, *args, **kwargs):
        self.event = self.request.META.get(GitHubHTTPHeaders.EVENT)
        log.info(
            "GitHub Webhook Handler invoked",
            extra=dict(
                github_webhook_event=self.event,
                delivery=self.request.META.get(GitHubHTTPHeaders.DELIVERY_TOKEN),
            ),
        )

        self.validate_signature(request)

        handler = getattr(self, self.event, self.unhandled_webhook_event)
        return handler(request, *args, **kwargs)

        return Response()
