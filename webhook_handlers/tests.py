import uuid
from unittest.mock import patch

from rest_framework.test import APITestCase
from rest_framework.reverse import reverse
from rest_framework import status

from core.tests.factories import RepositoryFactory
from core.models import Repository
from codecov_auth.tests.factories import OwnerFactory

from .constants import GitHubHTTPHeaders, GitHubWebhookEvents


class GithubWebhookHandlerTests(APITestCase):
    def _post_event_data(self, event, data={}):
        return self.client.post(
            reverse("github-webhook"),
            **{
                GitHubHTTPHeaders.EVENT: event,
                GitHubHTTPHeaders.DELIVERY_TOKEN: uuid.UUID(int=5),
                GitHubHTTPHeaders.SIGNATURE: 0
            },
            data=data,
            format="json"
        )

    def setUp(self):
        self.repo = RepositoryFactory(author=OwnerFactory(service="github"))

    def test_ping_returns_pong_and_200(self):
        response = self._post_event_data(event=GitHubWebhookEvents.PING)
        assert response.status_code == status.HTTP_200_OK

    def test_repository_publicized_sets_activated_false_and_private_false(self):
        self.repo.private = True
        self.repo.activated = True

        self.repo.save()

        response = self._post_event_data(
            event=GitHubWebhookEvents.REPOSITORY,
            data={
                "action": "publicized",
                "repository": {
                    "id": self.repo.service_id
                }
            }
        )

        assert response.status_code == status.HTTP_200_OK

        self.repo.refresh_from_db()

        assert self.repo.private == False
        assert self.repo.activated == False

    def test_repository_privatized_sets_private_true(self):
        self.repo.private = False
        self.repo.save()

        response = self._post_event_data(
            event=GitHubWebhookEvents.REPOSITORY,
            data={
                "action": "privatized",
                "repository": {
                    "id": self.repo.service_id
                }
            }
        )

        assert response.status_code == status.HTTP_200_OK

        self.repo.refresh_from_db()

        assert self.repo.private == True

    @patch('archive.services.ArchiveService.create_root_storage', lambda _: None)
    @patch('archive.services.ArchiveService.delete_repo_files', lambda _: None)
    def test_repository_deleted_deletes_repo(self):
        repository_id = self.repo.repoid

        response = self._post_event_data(
            event=GitHubWebhookEvents.REPOSITORY,
            data={
                "action": "deleted",
                "repository": {
                    "id": self.repo.service_id
                }
            }
        )

        assert response.status_code == status.HTTP_200_OK
        assert not Repository.objects.filter(repoid=repository_id).exists()

    @patch('archive.services.ArchiveService.create_root_storage', lambda _: None)
    @patch('archive.services.ArchiveService.delete_repo_files')
    def test_repository_delete_deletes_archive_data(self, delete_files_mock):
        response = self._post_event_data(
            event=GitHubWebhookEvents.REPOSITORY,
            data={
                "action": "deleted",
                "repository": {
                    "id": self.repo.service_id
                }
            }
        )

        delete_files_mock.assert_called_once()
