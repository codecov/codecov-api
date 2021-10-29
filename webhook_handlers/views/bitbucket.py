import logging

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from shared.helpers.yaml import walk

from codecov_auth.models import Owner
from core.models import Branch, Commit, Pull, PullStates, Repository
from services.task import TaskService
from webhook_handlers.constants import (
    BitbucketHTTPHeaders,
    BitbucketWebhookEvents,
    WebhookHandlerErrorMessages,
)

log = logging.getLogger(__name__)


class BitbucketWebhookHandler(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        self.event = self.request.META.get(BitbucketHTTPHeaders.EVENT)
        event_hook_id = self.request.META.get(BitbucketHTTPHeaders.UUID)

        repo = get_object_or_404(
            Repository,
            author__service="bitbucket",
            service_id=self.request.data["repository"]["uuid"][1:-1],
            hookid=event_hook_id,
        )
        if not repo.active:
            return Response(data=WebhookHandlerErrorMessages.SKIP_NOT_ACTIVE)

        log.info(
            "Bitbucket webhook message received",
            extra=dict(event=self.event, hookid=event_hook_id, repoid=repo.repoid),
        )

        if self.event == BitbucketWebhookEvents.PULL_REQUEST_CREATED:
            return self._handle_pull_request_created_event(repo)
        elif self.event in (
            BitbucketWebhookEvents.PULL_REQUEST_FULFILLED,
            BitbucketWebhookEvents.PULL_REQUEST_REJECTED,
        ):
            return self._handle_pull_request_state_change(repo)
        elif self.event == BitbucketWebhookEvents.REPO_PUSH:
            return self._handle_repo_push_event(repo)
        elif self.event in (
            BitbucketWebhookEvents.REPO_COMMIT_STATUS_CREATED,
            BitbucketWebhookEvents.REPO_COMMIT_STATUS_UPDATED,
        ):
            return self._handle_repo_commit_status_change(repo)

        return Response()

    def _handle_pull_request_created_event(self, repo):
        TaskService().pulls_sync(
            repoid=repo.repoid, pullid=self.request.data["pullrequest"]["id"]
        )
        return Response(data="Opening pull request in Codecov")

    def _handle_pull_request_state_change(self, repo):
        state = {
            BitbucketWebhookEvents.PULL_REQUEST_FULFILLED: PullStates.MERGED,
            BitbucketWebhookEvents.PULL_REQUEST_REJECTED: PullStates.CLOSED,
        }.get(self.event)

        Pull.objects.filter(
            repository__repoid=repo.repoid,
            pullid=self.request.data["pullrequest"]["id"],
        ).update(state=state)

        return Response()

    def _handle_repo_push_event(self, repo):
        for change in self.request.data["push"]["changes"]:
            if walk(change, ("old", "type")) == "branch" and change["new"] is None:
                # when a branch is deleted, new is null
                branch_name = change["old"]["name"]
                Branch.objects.filter(repository=repo, name=branch_name).delete()

        for change in self.request.data["push"]["changes"]:
            if change["new"]:
                if change["new"]["type"] == "branch" and (
                    repo.cache and repo.cache.get("yaml")
                ):
                    return Response(data="Synchronize codecov.yml")
                else:
                    return Response(data="Synchronize codecov.yml skipped")

        return Response()

    def _handle_repo_commit_status_change(self, repo):
        if self.request.data["commit_status"]["key"].startswith("codecov"):
            # a codecov/* context
            return Response(data=WebhookHandlerErrorMessages.SKIP_CODECOV_STATUS)

        if self.request.data["commit_status"]["state"] == "INPROGRESS":
            # skip pending
            return Response(data=WebhookHandlerErrorMessages.SKIP_PENDING_STATUSES)

        commitid = self.request.data["commit_status"]["links"]["commit"]["href"].split(
            "/"
        )[-1]

        if not Commit.objects.filter(
            repository=repo, commitid=commitid, state=Commit.CommitStates.COMPLETE
        ).exists():
            return Response(data=WebhookHandlerErrorMessages.SKIP_PROCESSING)

        TaskService().notify(repoid=repo.repoid, commitid=commitid)
        return Response(data="Notify queued")
