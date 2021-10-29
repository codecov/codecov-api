import logging

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from codecov_auth.models import Owner
from core.models import Branch, Commit, Pull, PullStates, Repository
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

    def post(self, request, *args, **kwargs):
        event = self.request.META.get(GitLabHTTPHeaders.EVENT)
        repo = None

        log.info("GitLab webhook message received", extra=dict(event=event))

        project_id = request.data.get("project_id") or request.data.get(
            "object_attributes", {}
        ).get("target_project_id")
        if project_id and request.data.get("event_name") != "project_create":
            # make sure the repo exists in the repos table
            repo = get_object_or_404(
                Repository, author__service="gitlab", service_id=project_id
            )

        if event == GitLabWebhookEvents.PUSH:
            return self._handle_push_event(repo)
        elif event == GitLabWebhookEvents.JOB:
            return self._handle_job_event(repo)
        elif event == GitLabWebhookEvents.MERGE_REQUEST:
            return self._handle_merge_request_event(repo)
        elif event == GitLabWebhookEvents.SYSTEM:
            return self._handle_system_hook_event(repo)

        return Response()

    def _handle_push_event(self, repo):
        """
        Triggered when pushing to the repository except when pushing tags.

        https://docs.gitlab.com/ce/user/project/integrations/webhooks.html#push-events
        """
        if not (repo.cache and repo.cache.get("yaml")):
            message = "No yaml cached yet."
        else:
            message = "Synchronize codecov.yml"
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

    def _handle_system_hook_event(self, repo):
        """
        GitLab Enterprise instance can send system hooks for changes on user, group, project, etc

        http://doc.gitlab.com/ee/system_hooks/system_hooks.html
        """
        if not get_config("setup", "enterprise_license"):
            raise PermissionDenied("No enterprise license detected")

        event_name = self.request.data.get("event_name")
        message = None

        if event_name == "project_create":
            owner_username, repo_name = self.request.data.get(
                "path_with_namespace"
            ).split("/", 2)

            try:
                owner = Owner.objects.get(service="gitlab", username=owner_username)

                obj, created = Repository.objects.get_or_create(
                    author=owner,
                    service_id=self.request.data.get("project_id"),
                    name=repo_name,
                    private=self.request.data.get("project_visibility") == "private",
                )
                message = "Repository created"
            except Owner.DoesNotExist:
                message = "Repository not created - unknown owner"

        elif event_name == "project_destroy":
            repo.deleted = True
            repo.activated = False
            repo.active = False
            repo.save(update_fields=["deleted", "activated", "active"])
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
                service="gitlab", username=owner_username
            ).first()

            if new_owner:
                repo.author = new_owner
                repo.name = repo_name
                repo.save(update_fields=["author", "name"])
            message = "Repository transfered"

        elif event_name == "user_create":
            obj, created = Owner.objects.update_or_create(
                service="gitlab",
                service_id=self.request.data.get("user_id"),
                username=self.request.data.get("username"),
                email=self.request.data.get("email"),
                name=self.request.data.get("name"),
            )
            message = "User created"

        elif (
            event_name in ("user_add_to_team", "user_remove_from_team")
            and self.request.data.get("project_visibility") == "private"
        ):
            user = Owner.objects.filter(
                service="gitlab",
                service_id=self.request.data.get("user_id"),
                oauth_token__isnull=False,
            ).first()

            if user:
                if event_name == "user_add_to_team":
                    user.permission = list(
                        set((user.permission or []) + [int(repo.repoid)])
                    )
                    user.save(update_fields=["permission"])
                    message = "Permission added"
                else:
                    new_permissions = set((user.permission or []))
                    new_permissions.remove(int(repo.repoid))
                    user.permission = list(new_permissions)
                    user.save(update_fields=["permission"])
                    message = "Permission removed"
            else:
                message = "User not found or not active"

        return Response(data=message)
