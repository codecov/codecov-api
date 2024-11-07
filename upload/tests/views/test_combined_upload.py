from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from shared.django_apps.core.tests.factories import (
    RepositoryFactory,
)

from core.models import Commit
from reports.models import (
    CommitReport,
    ReportSession,
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
        assert "commit_sha" in response.json()

    def test_get_repo_not_found(self, db):
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
        assert response.status_code == 400
        assert "Repository not found" in str(response.json())

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

    @patch("services.task.TaskService.update_commit")
    def test_successful_combined_upload(self, mock_update_commit, db):
        repository = RepositoryFactory(
            name="the_repo", author__username="codecov", author__service="github"
        )
        repository.save()
        repo_slug = f"{repository.author.username}::::{repository.name}"
        url = reverse(
            "new_upload.combined_upload",
            args=[repository.author.service, repo_slug],
        )

        upload_data = {
            "commit_sha": "abc123",
            "branch": "main",
            "pull_request_number": "42",
            "code": "coverage-data",
            "build_code": "build-1",
            "build_url": "http://ci.test/build/1",
            "job_code": "job-1",
            "flags": ["unit", "integration"],
            "name": "Upload 1",
        }

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="token " + repository.upload_token)
        response = client.post(url, upload_data, format="json")

        assert response.status_code == 201

        # Verify commit was created
        commit = Commit.objects.get(commitid="abc123")
        assert commit.branch == "main"
        assert commit.pullid == 42
        assert commit.repository == repository

        # Verify report was created
        report = CommitReport.objects.get(commit=commit)
        assert report is not None

        # Verify upload was created
        session = ReportSession.objects.get(report=report)
        assert session.build_code == "build-1"
        assert session.build_url == "http://ci.test/build/1"
        assert session.job_code == "job-1"
        assert session.name == "Upload 1"

        mock_update_commit.assert_called_with(
            commitid="abc123", repoid=repository.repoid
        )

    @pytest.mark.parametrize("branch", ["main", "someone:main", "someone/fork:main"])
    @pytest.mark.parametrize("private", [True, False])
    def test_combined_upload_tokenless(self, db, branch, private):
        repository = RepositoryFactory(
            private=private, author__username="codecov", name="the_repo"
        )
        repo_slug = f"{repository.author.username}::::{repository.name}"
        url = reverse(
            "new_upload.combined_upload",
            args=[repository.author.service, repo_slug],
        )

        upload_data = {
            "commit_sha": "abc123",
            "branch": branch,
            "code": "coverage-data",
        }

        client = APIClient()
        response = client.post(url, upload_data, format="json")

        if ":" in branch and private == False:
            assert response.status_code == 201
            commit = Commit.objects.get(commitid="abc123")
            assert commit.branch == branch
        else:
            assert response.status_code == 401
            assert not Commit.objects.filter(commitid="abc123").exists()

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
        assert "commit_sha" in response.json()

        # Invalid flag format
        response = client.post(
            url, {"commit_sha": "abc123", "flags": "not-a-list"}, format="json"
        )
        assert response.status_code == 400
        assert "flags" in response.json()
