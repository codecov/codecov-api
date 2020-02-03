import logging

from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from .constants import GitHubHTTPHeaders, GitHubWebhookEvents


log = logging.getLogger(__name__)


class GithubWebhookHandler(APIView):
    permission_classes = [AllowAny]

    def _validate_signature(self, request):
        pass

    def _handle_ping(self):
        log.info("GitHub Webhook Handler PING")
        return Response(status=status.HTTP_200_OK, data="pong")

    def post(self, request, *args, **kwargs):
        self._validate_signature(request)

        event = self.request.META.get(GitHubHTTPHeaders.EVENT)

        if event == GitHubWebhookEvents.PING:
            return self._handle_ping()
