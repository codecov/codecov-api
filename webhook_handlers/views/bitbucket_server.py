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
    BitbucketServerHTTPHeaders,
    BitbucketServerWebhookEvents,
    WebhookHandlerErrorMessages,
)

log = logging.getLogger(__name__)


class BitbucketServerWebhookHandler(APIView):
    # https://confluence.atlassian.com/bitbucketserver/event-payload-938025882.html
    permission_classes = [AllowAny]

    def _get_repo(self, event, body):
        if event.startswith("repo:"):
            repo_id = body["repository"]["id"]
        elif event.startswith("pr:"):
            repo_id = body["pullRequest"]["toRef"]["repository"]["id"]

        return get_object_or_404(
            Repository, author__service="bitbucket_server", service_id=repo_id
        )

    def post(self, request, *args, **kwargs):
        self.event = self.request.META.get(BitbucketServerHTTPHeaders.EVENT)
        event_hook_id = self.request.META.get(BitbucketServerHTTPHeaders.UUID)

        repo = self._get_repo(self.event, self.request.data)
        if not repo.active:
            return Response(data=WebhookHandlerErrorMessages.SKIP_NOT_ACTIVE)

        log.info(
            "BitbucketServer webhook message received",
            extra=dict(event=self.event, hookid=event_hook_id, repoid=repo.repoid),
        )

        if self.event == BitbucketServerWebhookEvents.PULL_REQUEST_CREATED:
            return self._handle_pull_request_created_event(repo)
        elif self.event in (
            BitbucketServerWebhookEvents.PULL_REQUEST_MERGED,
            BitbucketServerWebhookEvents.PULL_REQUEST_REJECTED,
        ):
            return self._handle_pull_request_state_change(repo)
        elif self.event == BitbucketServerWebhookEvents.REPO_REFS_CHANGED:
            return self._handle_repo_refs_change(repo)

        return Response()

    def _handle_pull_request_created_event(self, repo):
        TaskService().pulls_sync(
            repoid=repo.repoid, pullid=self.request.data["pullRequest"]["id"]
        )
        return Response(data="Opening pull request in Codecov")

    def _handle_pull_request_state_change(self, repo):
        state = {
            BitbucketServerWebhookEvents.PULL_REQUEST_MERGED: PullStates.MERGED,
            BitbucketServerWebhookEvents.PULL_REQUEST_DELETED: PullStates.CLOSED,
            BitbucketServerWebhookEvents.PULL_REQUEST_REJECTED: PullStates.CLOSED,
        }.get(self.event)

        Pull.objects.filter(
            repository__repoid=repo.repoid,
            pullid=self.request.data["pullRequest"]["id"],
        ).update(state=state)

        return Response()

    def _handle_repo_refs_change(self, repo):
        ref_type = self.request.data["push"]["changes"]["old"]["type"]
        if ref_type == "branch":
            Branch.objects.filter(
                repository=repo,
                name=self.request.data["push"]["changes"]["old"]["name"],
            ).delete()
        if self.request.data["push"]["changes"]["new"]:
            if (
                self.request.data["push"]["changes"]["new"]["type"] == "branch"
                and repo.cache
                and "yaml" in repo.cache
            ):
                return Response(data="Synchronize codecov.yml")
            else:
                return Response(data="Synchronize codecov.yml skipped")
        return Response()
