from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from freezegun import freeze_time
from rest_framework import status
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory

from codecov.tests.base_test import InternalAPITest
from reports.tests.factories import TestInstanceFactory
from utils.test_utils import APIClient


@freeze_time("2022-01-01T00:00:00")
class TestResultsViewsetTests(InternalAPITest):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org)
        self.current_owner = OwnerFactory(
            permission=[self.repo.repoid], organizations=[self.org.ownerid]
        )
        self.test_instances = [
            TestInstanceFactory(repoid=self.repo.repoid, commitid="1234"),
            TestInstanceFactory(repoid=self.repo.repoid, commitid="3456"),
        ]

        self.client = APIClient()
        self.client.force_login_owner(self.current_owner)

    def test_list(self):
        url = reverse(
            "api-v2-tests-results-list",
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "repo_name": self.repo.name,
            },
        )
        res = self.client.get(url)
        assert res.status_code == status.HTTP_200_OK
        assert res.json() == {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": self.test_instances[0].id,
                    "name": self.test_instances[0].test.name,
                    "test_id": self.test_instances[0].test_id,
                    "failure_message": self.test_instances[0].failure_message,
                    "duration_seconds": self.test_instances[0].duration_seconds,
                    "commitid": self.test_instances[0].commitid,
                    "outcome": self.test_instances[0].outcome,
                    "branch": self.test_instances[0].branch,
                    "repoid": self.test_instances[0].repoid,
                },
                {
                    "id": self.test_instances[1].id,
                    "name": self.test_instances[1].test.name,
                    "test_id": self.test_instances[1].test_id,
                    "failure_message": self.test_instances[1].failure_message,
                    "duration_seconds": self.test_instances[1].duration_seconds,
                    "commitid": self.test_instances[1].commitid,
                    "outcome": self.test_instances[1].outcome,
                    "branch": self.test_instances[1].branch,
                    "repoid": self.test_instances[1].repoid,
                },
            ],
            "total_pages": 1,
        }

    def test_list_filters(self):
        url = reverse(
            "api-v2-tests-results-list",
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "repo_name": self.repo.name,
            },
        )
        res = self.client.get(f"{url}?commit_id={self.test_instances[0].commitid}")
        assert res.status_code == status.HTTP_200_OK
        assert res.json() == {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "id": self.test_instances[0].id,
                    "name": self.test_instances[0].test.name,
                    "test_id": self.test_instances[0].test_id,
                    "failure_message": self.test_instances[0].failure_message,
                    "duration_seconds": self.test_instances[0].duration_seconds,
                    "commitid": self.test_instances[0].commitid,
                    "outcome": self.test_instances[0].outcome,
                    "branch": self.test_instances[0].branch,
                    "repoid": self.test_instances[0].repoid,
                },
            ],
            "total_pages": 1,
        }

    @patch("api.shared.repo.repository_accessors.RepoAccessors.get_repo_permissions")
    def test_retrieve(self, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)
        res = self.client.get(
            reverse(
                "api-v2-tests-results-detail",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                    "pk": self.test_instances[0].pk,
                },
            )
        )
        assert res.status_code == status.HTTP_200_OK
        assert res.json() == {
            "id": self.test_instances[0].id,
            "name": self.test_instances[0].test.name,
            "test_id": self.test_instances[0].test_id,
            "failure_message": self.test_instances[0].failure_message,
            "duration_seconds": self.test_instances[0].duration_seconds,
            "commitid": self.test_instances[0].commitid,
            "outcome": self.test_instances[0].outcome,
            "branch": self.test_instances[0].branch,
            "repoid": self.test_instances[0].repoid,
        }

    @patch("api.shared.permissions.RepositoryArtifactPermissions.has_permission")
    @patch("api.shared.permissions.SuperTokenPermissions.has_permission")
    def test_no_test_result_if_unauthenticated_token_request(
        self,
        super_token_permissions_has_permission,
        repository_artifact_permissions_has_permission,
    ):
        repository_artifact_permissions_has_permission.return_value = False
        super_token_permissions_has_permission.return_value = False

        url = reverse(
            "api-v2-tests-results-list",
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "repo_name": self.repo.name,
            },
        )
        res = self.client.get(f"{url}?commit_id={self.test_instances[0].commitid}")

        assert res.status_code == 403
        assert (
            res.data["detail"] == "You do not have permission to perform this action."
        )

    @override_settings(SUPER_API_TOKEN="testaxs3o76rdcdpfzexuccx3uatui2nw73r")
    @patch("api.shared.permissions.RepositoryArtifactPermissions.has_permission")
    def test_no_result_if_not_super_token_nor_user_token(
        self, repository_artifact_permissions_has_permission
    ):
        repository_artifact_permissions_has_permission.return_value = False

        res = self.client.get(
            reverse(
                "api-v2-tests-results-detail",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                    "pk": self.test_instances[0].pk,
                },
            ),
            HTTP_AUTHORIZATION="Bearer 73c8d301-2e0b-42c0-9ace-95eef6b68e86",
        )
        assert res.status_code == 401
        assert res.data["detail"] == "Invalid token."

    @override_settings(SUPER_API_TOKEN="testaxs3o76rdcdpfzexuccx3uatui2nw73r")
    @patch("api.shared.permissions.RepositoryArtifactPermissions.has_permission")
    def test_no_result_if_super_token_but_no_GET_request(
        self, repository_artifact_permissions_has_permission
    ):
        repository_artifact_permissions_has_permission.return_value = False
        res = self.client.post(
            reverse(
                "api-v2-tests-results-detail",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                    "pk": self.test_instances[0].pk,
                },
            ),
            HTTP_AUTHORIZATION="Bearer testaxs3o76rdcdpfzexuccx3uatui2nw73r",
        )
        assert res.status_code == 403
        assert (
            res.data["detail"] == "You do not have permission to perform this action."
        )

    @override_settings(SUPER_API_TOKEN="testaxs3o76rdcdpfzexuccx3uatui2nw73r")
    @patch("api.shared.permissions.RepositoryArtifactPermissions.has_permission")
    def test_result_with_valid_super_token(
        self, repository_artifact_permissions_has_permission
    ):
        repository_artifact_permissions_has_permission.return_value = False
        res = self.client.get(
            reverse(
                "api-v2-tests-results-detail",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                    "pk": self.test_instances[0].pk,
                },
            ),
            HTTP_AUTHORIZATION="Bearer testaxs3o76rdcdpfzexuccx3uatui2nw73r",
        )
        assert res.status_code == 200
        assert res.json() == {
            "id": self.test_instances[0].id,
            "name": self.test_instances[0].test.name,
            "test_id": self.test_instances[0].test_id,
            "failure_message": self.test_instances[0].failure_message,
            "duration_seconds": self.test_instances[0].duration_seconds,
            "commitid": self.test_instances[0].commitid,
            "outcome": self.test_instances[0].outcome,
            "branch": self.test_instances[0].branch,
            "repoid": self.test_instances[0].repoid,
        }
