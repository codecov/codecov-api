import json

from unittest.mock import patch, call

from rest_framework.test import APITestCase
from rest_framework.reverse import reverse

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import (
    RepositoryFactory,
    PullFactory,
    CommitFactory,
)

get_permissions_method = (
    "internal_api.repo.repository_accessors.RepoAccessors.get_repo_permissions"
)


@patch(get_permissions_method)
class PullViewSetTests(APITestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov", service="github")
        other_org = OwnerFactory(username="other_org")
        # Create different types of repos / pulls
        self.repo = RepositoryFactory(author=self.org, name="testRepoName", active=True)
        other_repo = RepositoryFactory(
            author=other_org, name="otherRepoName", active=True
        )
        repo_with_permission = [self.repo.repoid]
        self.user = OwnerFactory(
            username="codecov-user",
            service="github",
            organizations=[self.org.ownerid],
            permission=repo_with_permission,
        )
        PullFactory(
            pullid=10,
            author=self.org,
            repository=self.repo,
            state="open",
            head=CommitFactory(repository=self.repo, author=self.user).commitid,
            base=CommitFactory(repository=self.repo, author=self.user).commitid,
        )
        PullFactory(pullid=11, author=self.org, repository=self.repo, state="closed")
        PullFactory(pullid=12, author=other_org, repository=other_repo)
        self.correct_kwargs = {
            "service": "github",
            "owner_username": "codecov",
            "repo_name": "testRepoName",
        }
        self.incorrect_kwargs = {
            "service": "github",
            "owner_username": "codecov",
            "repo_name": "otherRepoName",
        }

    def test_get_pulls(self, mock_provider):
        mock_provider.return_value = True, True
        self.client.force_login(user=self.user)
        response = self.client.get(
            reverse("pulls-list", kwargs=self.correct_kwargs, current_app="api")
        )
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(
            len(content["results"]),
            3,
            "got the wrong number of pulls: {}".format(content["results"]),
        )

    def test_get_pulls_no_permissions(self, mock_provider):
        mock_provider.return_value = False, False
        self.user.permission = []
        self.user.save()
        self.client.force_login(user=self.user)
        response = self.client.get(
            reverse("pulls-list", kwargs=self.correct_kwargs, current_app="api")
        )
        self.assertEqual(response.status_code, 404)

    def test_get_pull_wrong_org(self, mock_provider):
        mock_provider.return_value = True, True
        self.client.force_login(user=self.user)
        response = self.client.get(
            reverse("pulls-list", kwargs=self.incorrect_kwargs, current_app="api")
        )
        content = json.loads(response.content.decode())
        self.assertEqual(
            response.status_code, 404, "got unexpected response: {}".format(content)
        )

    def test_can_get_public_repo_pull_detail_when_not_authenticated(
        self, mock_provider
    ):
        self.client.logout()
        mock_provider.return_value = True, True
        author = OwnerFactory()
        repo = RepositoryFactory(private=False, author=author)
        pull = PullFactory(repository=repo)
        response = self.client.get(
            reverse(
                "pulls-detail",
                kwargs={
                    "service": author.service,
                    "owner_username": author.username,
                    "repo_name": repo.name,
                    "pk": pull.pullid,
                },
            )
        )
        assert response.status_code == 200
        assert response.data["pullid"] == pull.pullid

    def test_get_pull(self, mock_provider):
        mock_provider.return_value = True, True
        self.client.force_login(user=self.user)
        response = self.client.get("/internal/github/codecov/testRepoName/pulls/10/")
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(content["pullid"], 10)

    def test_get_pull_no_permissions(self, mock_provider):
        self.user.permission = []
        self.user.save()
        mock_provider.return_value = False, False
        self.client.force_login(user=self.user)
        response = self.client.get("/api/github/codecov/testRepoName/pulls/10/")
        self.assertEqual(response.status_code, 404)

    @patch("services.task.TaskService.pulls_sync")
    def test_update_pull_user_provided_base(self, pulls_sync_mock, mock_provider):
        mock_provider.return_value = True, True
        self.client.force_login(user=self.user)
        response = self.client.put(
            "/api/github/codecov/testRepoName/pulls/10/",
            {"user_provided_base_sha": "new-sha"},
        )
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content.decode())
        self.assertEqual(content["user_provided_base_sha"], "new-sha")
        pulls_sync_mock.assert_called_once_with(repoid=self.repo.repoid, pullid="10")

    def test_update_pull_user_provided_base_no_permissions(self, mock_provider):
        mock_provider.return_value = False, False
        self.user.permission = []
        self.user.save()
        self.client.force_login(user=self.user)
        response = self.client.put(
            "/api/github/codecov/testRepoName/pulls/10/",
            {"user_provided_base_sha": "new-sha"},
        )
        self.assertEqual(response.status_code, 404)
        
