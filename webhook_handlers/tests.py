import uuid

from rest_framework.test import APITestCase
from rest_framework.reverse import reverse
from rest_framework import status

from .constants import GitHubHTTPHeaders, GitHubWebhookEvents


class GithubWebhookHandlerTests(APITestCase):
    def _post_event_data(self, event):
        return self.client.post(
            reverse("github-webhook"),
            **{
                GitHubHTTPHeaders.EVENT: event,
                GitHubHTTPHeaders.DELIVERY_TOKEN: uuid.UUID(int=5),
                GitHubHTTPHeaders.SIGNATURE: 0
            },
            content_type="application/json",
            data={}
        )

    def test_ping_returns_pong_and_200(self):
        response = self._post_event_data(event=GitHubWebhookEvents.PING)
        assert response.status_code == status.HTTP_200_OK
        assert response.data == 'pong'
