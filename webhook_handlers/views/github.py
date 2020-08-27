import logging
import re
import hmac
from hashlib import sha1

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, NotFound

from core.models import Repository, Branch, Commit, Pull
from codecov_auth.models import Owner
from services.archive import ArchiveService
from services.redis import get_redis_connection
from services.task import TaskService
from utils.config import get_config

from webhook_handlers.constants import GitHubHTTPHeaders, GitHubWebhookEvents, WebhookHandlerErrorMessages


log = logging.getLogger(__name__)


# This should probably go somewhere where it can be easily shared
regexp_ci_skip = re.compile(r'\[(ci|skip| |-){3,}\]').search


class GithubWebhookHandler(APIView):
    """
    GitHub Webhook Handler. Method names correspond to events as defined in

        webhook_handlers.constants.GitHubWebhookEvents
    """
    permission_classes = [AllowAny]
    redis = get_redis_connection()

    def validate_signature(self, request):
        key = get_config(
            "github",
            'webhook_secret',
            default=b'testixik8qdauiab1yiffydimvi72ekq'
        )
        if type(key) is str:
            # If "key" comes from k8s secret, it is of type str, so
            # must convert to bytearray for use with hmac
            key = bytes(key, 'utf-8')

        sig = 'sha1='+hmac.new(
            key,
            request.body,
            digestmod=sha1
        ).hexdigest()

        if sig != request.META.get(GitHubHTTPHeaders.SIGNATURE):
            raise PermissionDenied()

    def unhandled_webhook_event(self, request, *args, **kwargs):
        return Response(data=WebhookHandlerErrorMessages.UNSUPPORTED_EVENT)

    def _get_repo(self, request):
        try:
            return Repository.objects.get(
                author__service="github",
                service_id=self.request.data.get("repository", {}).get("id")
            )
        except Repository.DoesNotExist:
            raise NotFound("Repo does not exist")

    def ping(self, request, *args, **kwargs):
        return Response(data="pong")

    def repository(self, request, *args, **kwargs):
        action, repo = self.request.data.get('action'), self._get_repo(request)
        if action == "publicized":
            repo.private, repo.activated = False, False
            repo.save()
        elif action == "privatized":
            repo.private = True
            repo.save()
        elif action == "deleted":
            log.info(f"Request to delete repository: {repo.repoid}")
            repo.deleted = True
            repo.activated = False
            repo.active = False
            repo.save(update_fields=["deleted", "activated", "active"])
            log.info(f"Repository {repo.repoid} soft-deleted")
        else:
            log.warn("Unknown 'repository' action: %s", action)
        return Response()

    def delete(self, request, *args, **kwargs):
        ref_type = request.data.get("ref_type")
        if ref_type != "branch":
            return Response(f"Unsupported ref type: {ref_type}")
        branch_name = self.request.data.get('ref')[11:]
        Branch.objects.filter(repository=self._get_repo(request), name=branch_name).delete()
        return Response()

    def public(self, request, *args, **kwargs):
        repo = self._get_repo(request)
        repo.private, repo.activated = False, False
        repo.save()
        return Response()

    def push(self, request, *args, **kwargs):
        ref_type = "branch" if request.data.get("ref")[5:10] == "heads" else "tag"
        repo = self._get_repo(request)
        if ref_type != "branch":
            log.info("Ref is tag, not branch, ignoring push event", extra=dict(repoid=repo.repoid))
            return Response(f"Unsupported ref type: {ref_type}")

        if not repo.active:
            log.info("Repo is not active, ignoring push event", extra=dict(repoid=repo.repoid))
            return Response(data=WebhookHandlerErrorMessages.SKIP_NOT_ACTIVE)

        branch_name = self.request.data.get('ref')[11:]
        commits = self.request.data.get('commits', [])

        if not commits:
            log.info(f"No commits in webhook payload for branch {branch_name}", extra=dict(repoid=repo.repoid))
            return Response()

        Commit.objects.filter(
            repository=repo,
            commitid__in=[commit.get('id') for commit in commits],
            merged=False
        ).update(branch=branch_name)

        log.info(f"Branch name updated for commits to {branch_name}", extra=dict(repoid=repo.repoid))

        most_recent_commit = commits[-1]

        if regexp_ci_skip(most_recent_commit.get('message')):
            log.info(
                "CI skip tag on head commit, not setting status",
                extra=dict(
                    repoid=repo.repoid,
                    commitid=most_recent_commit.get("id")
                )
            )
            return Response(data="CI Skipped")

        if self.redis.sismember('beta.pending', repo.repoid):
            log.info(
                "Triggering status set pending task",
                extra=dict(
                    repoid=repo.repoid,
                    commitid=most_recent_commit.get("id")
                )
            )
            TaskService().status_set_pending(
                repoid=repo.repoid,
                commitid=most_recent_commit.get('id'),
                branch=branch_name,
                on_a_pull_request=False
            )

        return Response()

    def status(self, request, *args, **kwargs):
        repo = self._get_repo(request)

        if not repo.active:
            return Response(data=WebhookHandlerErrorMessages.SKIP_NOT_ACTIVE)
        if request.data.get("context", "")[:8] == "codecov/":
            return Response(data=WebhookHandlerErrorMessages.SKIP_CODECOV_STATUS)
        if request.data.get("state") == "pending":
            return Response(data=WebhookHandlerErrorMessages.SKIP_PENDING_STATUSES)

        commitid = request.data.get("sha")
        if not Commit.objects.filter(repository=repo, commitid=commitid, state="complete").exists():
            return Response(data=WebhookHandlerErrorMessages.SKIP_PROCESSING)

        log.info("Triggering notification from webhook for github: %s", commitid)

        TaskService().notify(repoid=repo.repoid, commitid=commitid)

        return Response()

    def pull_request(self, request, *args, **kwargs):
        repo = self._get_repo(request)

        if not repo.active:
            return Response(data=WebhookHandlerErrorMessages.SKIP_NOT_ACTIVE)

        action, pullid = request.data.get("action"), request.data.get("number")

        if action in ["opened", "closed", "reopened", "synchronize"]:
            TaskService().pulls_sync(repoid=repo.repoid, pullid=pullid)
        elif action == "edited":
            Pull.objects.filter(
                repository=repo, pullid=pullid
            ).update(
                title=request.data.get("pull_request", {}).get("title")
            )

        return Response()

    def _handle_installation_events(self, request, *args, **kwargs):
        service_id = request.data["installation"]["account"]["id"]
        username = request.data["installation"]["account"]["login"]
        action = request.data.get("action")

        owner, _ = Owner.objects.get_or_create(
            service="github",
            service_id=service_id,
            username=username
        )

        if action == "deleted":
            owner.integration_id = None
            owner.save()
            owner.repository_set.all().update(using_integration=False, bot=None)
        else:
            if owner.integration_id is None:
                owner.integration_id = request.data["installation"]["id"]
                owner.save()

            TaskService().refresh(
                ownerid=owner.ownerid,
                username=username,
                sync_teams=False,
                sync_repos=True,
                using_integration=True
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
                f"from organization with service-id {request.data['organization']['id']}"
            )

            try:
                org = Owner.objects.get(
                    service="github",
                    service_id=request.data["organization"]["id"]
                )
            except Owner.DoesNotExist:
                log.info("Organization does not exist, exiting")
                return Response(
                    status=status.HTTP_400_BAD_REQUEST,
                    data="Attempted to remove member from non-Codecov org failed"
                )

            try:
                member = Owner.objects.get(
                    service="github",
                    service_id=request.data["membership"]["user"]["id"]
                )
            except Owner.DoesNotExist:
                log.info(
                    f"Member with service-id {request.data['membership']['user']['id']} "
                    f"does not exist, exiting",
                    extra=dict(ownerid=org.ownerid)
                )
                return Response(
                    status=status.HTTP_400_BAD_REQUEST,
                    data="Attempted to remove non Codecov user from Codecov org failed"
                )

            member.organizations = [ownerid for ownerid in member.organizations if ownerid != org.ownerid]
            member.save(update_fields=['organizations'])

            log.info(f"User removal of {member.ownerid}, success", extra=dict(ownerid=org.ownerid))

        return Response()

    def _handle_marketplace_events(self, request, *args, **kwargs):
        TaskService().sync_plans(
            sender=request.data["sender"],
            account=request.data["marketplace_purchase"]["account"],
            action=request.data["action"]
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
                extra=dict(repoid=repo.repoid)
            )
            try:
                member = Owner.objects.get(
                    service="github",
                    service_id=request.data["member"]["id"]
                )
            except Owner.DoesNotExist:
                log.info(
                    f"Repo permissions unchanged -- owner doesn't exist",
                    extra=dict(repoid=repo.repoid)
                )
                return Response(status=status.HTTP_404_NOT_FOUND)
            member.permission.remove(repo.repoid)
            member.save(update_fields=['permission'])
            log.info(
                f"Successfully updated read permissions for repo",
                extra=dict(repoid=repo.repoid, ownerid=member.ownerid)
            )
        return Response()

    def post(self, request, *args, **kwargs):
        self.validate_signature(request)

        event = self.request.META.get(GitHubHTTPHeaders.EVENT)
        log.info("GitHub Webhook Handler invoked with: %s", event.upper())
        handler = getattr(self, event, self.unhandled_webhook_event)

        return handler(request, *args, **kwargs)
