import logging

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from core.models import Repository, Branch
from archive.services import ArchiveService

from .constants import GitHubHTTPHeaders, GitHubWebhookEvents


log = logging.getLogger(__name__)


class GithubWebhookHandler(APIView):
    permission_classes = [AllowAny]

    def _validate_signature(self, request):
        pass

    def _handle_ping(self):
        return Response(status=status.HTTP_200_OK, data="pong")

    def _handle_repository(self, action, repo):
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

    def _handle_delete(self, repo, branch_name):
        Branch.objects.filter(repository=repo, name=branch_name).delete()

    def _handle_public(self, repo):
        repo.private, repo.activated = False, False
        repo.save()

    def post(self, request, *args, **kwargs):
        self._validate_signature(request)

        event = self.request.META.get(GitHubHTTPHeaders.EVENT)

        if event == GitHubWebhookEvents.PING:
            return self._handle_ping()

        action = request.data.get('action')
        repo = Repository.objects.get(
            author__service="github",
            service_id=self.request.data.get("repository", {}).get("id")
        )

        log.info("GitHub webhook handler invoked on '%s' with : '%s', '%s',", repo.repoid, event, action)

        if event == GitHubWebhookEvents.REPOSITORY:
            self._handle_repository(action, repo)
        elif event == GitHubWebhookEvents.DELETE:
            self._handle_delete(repo, self.request.data.get('ref')[11:])
        elif event == GitHubWebhookEvents.PUBLIC:
            self._handle_public(repo)
        return Response(status=status.HTTP_200_OK)
