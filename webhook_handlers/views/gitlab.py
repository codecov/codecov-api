import logging

from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.utils.crypto import constant_time_compare
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from codecov_auth.models import Owner
from core.models import Commit, Pull, PullStates, Repository
from services.refresh import RefreshService
from services.task import TaskService
from utils.config import get_config
from webhook_handlers.constants import (
    GitLabHTTPHeaders,
    GitLabWebhookEvents,
    WebhookHandlerErrorMessages,
)

log = logging.getLogger(__name__)


class GitLabWebhookHandler(APIView):
    permission_classes = [AllowAny]
    service_name = "gitlab"

    def post(self, request, *args, **kwargs):
        """
        Helpful docs for working with GitLab webhooks
        https://docs.gitlab.com/ee/user/project/integrations/webhooks.html#webhook-receiver-requirements
        for those special system hooks: https://docs.gitlab.com/ee/administration/system_hooks.html#hooks-request-example
        all the other hooks: https://docs.gitlab.com/ee/user/project/integrations/webhook_events.html
        """
        event = self.request.META.get(GitLabHTTPHeaders.EVENT)

        log.info("GitLab webhook message received", extra=dict(event=event))

        project_id = request.data.get("project_id") or request.data.get(
            "object_attributes", {}
        ).get("target_project_id")

        event_name = self.request.data.get("event_name")

        is_enterprise = True if get_config("setup", "enterprise_license") else False

        if event_name == "project_create":
            if event == GitLabWebhookEvents.SYSTEM and is_enterprise:
                return self._handle_system_project_create_hook_event()
            else:
                raise PermissionDenied()

        repo = get_object_or_404(
            Repository, author__service=self.service_name, service_id=project_id
        )

        webhook_validation = bool(
            get_config(self.service_name, "webhook_validation", default=True)
        )
        if webhook_validation:
            self._validate_secret(request, repo.webhook_secret)

        if event == GitLabWebhookEvents.PUSH:
            return self._handle_push_event(repo)
        elif event == GitLabWebhookEvents.JOB:
            return self._handle_job_event(repo)
        elif event == GitLabWebhookEvents.MERGE_REQUEST:
            return self._handle_merge_request_event(repo)
        elif event == GitLabWebhookEvents.SYSTEM:
            # SYSTEM events have always been gated behind is_enterprise: requires an enterprise_license
            if not is_enterprise:
                raise PermissionDenied()
            return self._handle_system_hook_event(repo, event_name)

        return Response()

    def _handle_push_event(self, repo):
        """
        Triggered when pushing to the repository except when pushing tags.

        https://docs.gitlab.com/ce/user/project/integrations/webhooks.html#push-events
        """
        message = "No yaml cached yet."
        return Response(data=message)

    def _handle_job_event(self, repo):
        """
        Triggered on status change of a job.

        This is equivalent to legacy "Build Hook" handling (https://gitlab.com/gitlab-org/gitlab-foss/issues/28226)

        https://docs.gitlab.com/ee/user/project/integrations/webhooks.html#job-events
        """
        if self.request.data.get("build_status") == "pending":
            return Response(data=WebhookHandlerErrorMessages.SKIP_PENDING_STATUSES)

        if repo.active is not True:
            return Response(data=WebhookHandlerErrorMessages.SKIP_PROCESSING)

        commitid = self.request.data.get("sha")

        try:
            commit = repo.commits.get(
                commitid=commitid, state=Commit.CommitStates.COMPLETE
            )
        except Commit.DoesNotExist:
            return Response(data=WebhookHandlerErrorMessages.SKIP_PROCESSING)

        TaskService().notify(repoid=commit.repository.repoid, commitid=commitid)
        return Response(data="Notify queued.")

    def _handle_merge_request_event(self, repo):
        """
        Triggered when a new merge request is created, an existing merge request was updated/merged/closed or
        a commit is added in the source branch.

        https://docs.gitlab.com/ce/user/project/integrations/webhooks.html#merge-request-events
        """
        repoid = repo.repoid

        pull = self.request.data.get("object_attributes", {})
        action = pull.get("action")
        message = None
        if action == "open":
            TaskService().pulls_sync(repoid=repoid, pullid=pull["iid"])
            message = "Opening pull request in Codecov"

        elif action == "close":
            Pull.objects.filter(repository__repoid=repoid, pullid=pull["iid"]).update(
                state=PullStates.CLOSED
            )
            message = "Pull request closed"

        elif action == "merge":
            TaskService().pulls_sync(repoid=repoid, pullid=pull["iid"])
            message = "Pull request merged"

        elif action == "update":
            TaskService().pulls_sync(repoid=repoid, pullid=pull["iid"])
            message = "Pull request synchronize queued"

        else:
            log.warning(
                "Unhandled Gitlab webhook merge_request action",
                extra=dict(action=action),
            )

        return Response(data=message)

    def _initiate_sync_for_owner(self, owner):
        RefreshService().trigger_refresh(
            ownerid=owner.ownerid,
            username=owner.username,
            using_integration=False,
            manual_trigger=False,
        )

    def _handle_system_project_create_hook_event(self):
        owner_username, _ = self.request.data.get("path_with_namespace").split("/", 2)

        try:
            owner = Owner.objects.get(
                service=self.service_name,
                username=owner_username,
                oauth_token__isnull=False,
            )
            self._initiate_sync_for_owner(owner)
        except Owner.DoesNotExist:
            pass

        return Response()

    def _handle_system_hook_event(self, repo, event_name):
        """
        GitLab Enterprise instance can send system hooks for changes on user, group, project, etc
        """
        message = None

        if event_name == "project_destroy":
            repo.deleted = True
            repo.activated = False
            repo.active = False
            repo.name = f"{repo.name}-deleted"
            repo.save(update_fields=["deleted", "activated", "active", "name"])
            message = "Repository deleted"

        elif event_name == "project_rename":
            new_name = self.request.data.get("path_with_namespace").split("/")[-1]
            repo.name = new_name
            repo.save(update_fields=["name"])
            message = "Repository renamed"

        elif event_name == "project_transfer":
            owner_username, repo_name = self.request.data.get(
                "path_with_namespace"
            ).split("/")
            new_owner = Owner.objects.filter(
                service=self.service_name, username=owner_username
            ).first()
            message = "Repository transferred"
            if new_owner:
                repo.author = new_owner
                repo.name = repo_name
                repo.save(update_fields=["author", "name"])

        elif (
            event_name in ("user_add_to_team", "user_remove_from_team")
            and self.request.data.get("project_visibility") == "private"
        ):
            user = Owner.objects.filter(
                service=self.service_name,
                service_id=self.request.data.get("user_id"),
                oauth_token__isnull=False,
            ).first()
            message = "Sync initiated"
            if user:
                self._initiate_sync_for_owner(owner=user)

        return Response(data=message)

    def _validate_secret(self, request: HttpRequest, webhook_secret: str):
        token = request.META.get(GitLabHTTPHeaders.TOKEN)
        if token and webhook_secret:
            if constant_time_compare(webhook_secret, token):
                return
        raise PermissionDenied()


class GitLabEnterpriseWebhookHandler(GitLabWebhookHandler):
    service_name = "gitlab_enterprise"
