import logging
import redis
import re

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from core.models import Repository, Branch, Commit
from archive.services import ArchiveService
from services.task import TaskService
from utils.config import get_config

from .constants import GitHubHTTPHeaders, GitHubWebhookEvents


log = logging.getLogger(__name__)


# This should probably go somewhere where it can be easily shared
regexp_ci_skip = re.compile(r'\[(ci|skip| |-){3,}\]').search


class GithubWebhookHandler(APIView):
    """
    GitHub Webhook Handler. Method names correspond to events as defined in

        webhook_handlers.constants.GitHubWebhookEvents
    """
    permission_classes = [AllowAny]
    redis = redis.Redis.from_url(get_config('services', 'redis_url'))

    def validate_signature(self, request):
        pass

    def _get_repo(self, request):
        return Repository.objects.get(
            author__service="github",
            service_id=self.request.data.get("repository", {}).get("id")
        )

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
            ArchiveService(repo).delete_repo_files()
            repo.delete()
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
        if ref_type != "branch":
            return Response(f"Unsupported ref type: {ref_type}")

        repo = self._get_repo(request)

        if not repo.active:
            return Response(data="Repository not active")

        branch_name = self.request.data.get('ref')[11:]
        commits = self.request.data.get('commits', [])

        if not commits:
            return Response()

        Commit.objects.filter(
            repository=repo,
            commitid__in=[commit.get('id') for commit in commits],
            merged=False
        ).update(branch=branch_name)

        most_recent_commit = commits[-1]

        if regexp_ci_skip(most_recent_commit.get('message')):
            return Response(data="CI Skipped")

        if self.redis.sismember('beta.pending', repo.repoid):
            TaskService().status_set_pending(
                repoid=repo.repoid,
                commitid=most_recent_commit.get('id'),
                branch=branch_name,
                on_a_pull_request=False
            )

        return Response()

    def unhandled_webhook_event(self, request, *args, **kwargs):
        pass

    def post(self, request, *args, **kwargs):
        self.validate_signature(request)

        self.event = self.request.META.get(GitHubHTTPHeaders.EVENT)
        log.info("GitHub Webhook Handler invoked with: %s", self.event.upper())
        handler = getattr(self, self.event, self.unhandled_webhook_event)

        return handler(request, *args, **kwargs)
