import json
from unittest.mock import call, patch

from rest_framework.test import APIClient, APITestCase

from codecov_auth.tests.factories import OwnerFactory
from core.models import Pull
from core.tests.factories import CommitFactory, PullFactory, RepositoryFactory


class PullViewSetTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = OwnerFactory(username="codecov", service="github")
        other_org = OwnerFactory(username="other_org")
        # Create different types of repos / pulls
        self.repo = RepositoryFactory(author=self.org, name="testRepoName", active=True)
        self.other_repo = RepositoryFactory(
            author=other_org, name="otherRepoName", active=True
        )
        repo_with_permission = [self.repo.repoid]
        self.user = OwnerFactory(
            username="codecov-user",
            service="github",
            organizations=[self.org.ownerid],
            permission=repo_with_permission,
        )
        self.open_pull = PullFactory(
            pullid=10,
            author=self.org,
            repository=self.repo,
            state="open",
            head=CommitFactory(repository=self.repo, author=self.user).commitid,
            base=CommitFactory(repository=self.repo, author=self.user).commitid,
        )
        PullFactory(pullid=11, author=self.org, repository=self.repo, state="closed")
        PullFactory(pullid=12, author=other_org, repository=self.other_repo)
        self.correct_kwargs = {
            "service": "github",
            "owner_username": "codecov",
            "repo_name": "testRepoName",
        }

    def test_get_pulls(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.repo.upload_token)
        response = self.client.get("/api/github/codecov/testRepoName/pulls/")
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(
            len(content["results"]),
            3,
            "got the wrong number of pulls: {}".format(content["results"]),
        )

    def test_get_pulls_wrong_repo_token(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.other_repo.upload_token
        )
        response = self.client.get("/api/github/codecov/testRepoName/pulls/")
        self.assertEqual(response.status_code, 403)

    def test_get_pulls_no_permissions(self):
        response = self.client.get("/api/github/codecov/testRepoName/pulls/")
        self.assertEqual(response.status_code, 401)

    def test_get_pull(self):
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.repo.upload_token)
        response = self.client.get("/api/github/codecov/testRepoName/pulls/10/")
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(content["pullid"], 10)

    def test_get_pull_no_permissions(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.other_repo.upload_token
        )
        response = self.client.get("/api/github/codecov/testRepoName/pulls/10/")
        self.assertEqual(response.status_code, 403)

    @patch("services.task.TaskService.pulls_sync")
    def test_update_pull_user_provided_base(self, pulls_sync_mock):
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.repo.upload_token)
        response = self.client.put(
            "/api/github/codecov/testRepoName/pulls/10/",
            {"user_provided_base_sha": "new-sha"},
        )
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(content["user_provided_base_sha"], "new-sha")
        self.assertEqual(
            Pull.objects.get(pullid=10, repository=self.repo).user_provided_base_sha,
            "new-sha",
        )
        pulls_sync_mock.assert_called_once_with(repoid=self.repo.repoid, pullid="10")

    def test_update_pull_user_provided_base_no_permissions(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Token " + self.other_repo.upload_token
        )
        response = self.client.put(
            "/api/github/codecov/testRepoName/pulls/10/",
            {"user_provided_base_sha": "new-sha"},
        )
        self.assertEqual(response.status_code, 403)

    @patch("services.task.TaskService.pulls_sync")
    def test_create_new_pull_user_provided_base(self, pulls_sync_mock):
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.repo.upload_token)
        self.client.force_login(user=self.user)
        response = self.client.put(
            "/api/github/codecov/testRepoName/pulls/15/",
            {"user_provided_base_sha": "new-sha"},
        )
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(content["user_provided_base_sha"], "new-sha")
        self.assertEqual(
            Pull.objects.get(pullid=15, repository=self.repo).user_provided_base_sha,
            "new-sha",
        )
        pulls_sync_mock.assert_called_once_with(repoid=self.repo.repoid, pullid="15")

    @patch("services.task.TaskService.pulls_sync")
    def test_post_pull_user_provided_base(self, pulls_sync_mock):
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.repo.upload_token)
        response = self.client.post(
            "/api/github/codecov/testRepoName/pulls/15/",
            {"user_provided_base_sha": "new-sha"},
        )
        self.assertEqual(response.status_code, 405)
        assert not pulls_sync_mock.called
