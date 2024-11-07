from unittest.mock import patch

from django.urls import reverse
from rest_framework.test import APIClient
from shared.django_apps.core.tests.factories import (
    RepositoryFactory,
)


class TestCombinedUpload:
    def test_get_repo(self, db):
        repository = RepositoryFactory(
            name="the_repo", author__username="codecov", author__service="github"
        )
        repository.save()
        repo_slug = f"{repository.author.username}::::{repository.name}"
        url = reverse(
            "new_upload.combined_upload",
            args=[repository.author.service, repo_slug],
        )
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="token " + repository.upload_token)
        response = client.post(url, {}, format="json")
        assert response.status_code == 400  # Bad request due to missing required fields
        assert "commitid" in response.json()

    @patch("services.task.TaskService.upload")
    def test_get_repo_not_found(self, upload, db):
        repository = RepositoryFactory(
            name="the_repo", author__username="codecov", author__service="github"
        )
        repo_slug = "codecov::::wrong-repo-name"
        url = reverse(
            "new_upload.combined_upload",
            args=[repository.author.service, repo_slug],
        )
        client = APIClient()
        response = client.post(url, {}, format="json")
        assert response.status_code == 401
        assert response.json() == {"detail": "Not valid tokenless upload"}
        assert not upload.called

    def test_deactivated_repo(self, db):
        repository = RepositoryFactory(
            name="the_repo",
            author__username="codecov",
            author__service="github",
            active=True,
            activated=False,
        )
        repository.save()
        repo_slug = f"{repository.author.username}::::{repository.name}"
        url = reverse(
            "new_upload.combined_upload",
            args=[repository.author.service, repo_slug],
        )
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="token " + repository.upload_token)
        response = client.post(url, {"commit_sha": "abc123"}, format="json")
        assert response.status_code == 400
        assert "This repository is deactivated" in str(response.json())

    def test_combined_upload_with_errors(self, db):
        repository = RepositoryFactory()
        repo_slug = f"{repository.author.username}::::{repository.name}"
        url = reverse(
            "new_upload.combined_upload",
            args=[repository.author.service, repo_slug],
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="token " + repository.upload_token)

        # Missing required fields
        response = client.post(url, {}, format="json")
        assert response.status_code == 400
        assert "commitid" in response.json()

        # Invalid flag format
        response = client.post(
            url, {"commit_sha": "abc123", "flags": "not-a-list"}, format="json"
        )
        assert response.status_code == 400
        assert "flags" in response.json()
