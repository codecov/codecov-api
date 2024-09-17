from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from freezegun import freeze_time

from codecov.tests.base_test import InternalAPITest
from codecov_auth.tests.factories import OwnerFactory
from core.models import Pull
from core.tests.factories import PullFactory, RepositoryFactory
from utils.test_utils import APIClient


@freeze_time("2022-01-01T00:00:00")
class PullViewsetTests(InternalAPITest):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org)
        self.current_owner = OwnerFactory(
            permission=[self.repo.repoid], organizations=[self.org.ownerid]
        )
        self.pulls = [
            PullFactory(repository=self.repo),
            PullFactory(repository=self.repo),
        ]
        Pull.objects.filter(pk=self.pulls[1].pk).update(
            updatestamp="2023-01-01T00:00:00"
        )

        self.client = APIClient()
        self.client.force_login_owner(self.current_owner)

    def test_list(self):
        res = self.client.get(
            reverse(
                "api-v2-pulls-list",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                },
            )
        )
        assert res.status_code == 200
        assert res.json() == {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {
                    "pullid": self.pulls[1].pullid,
                    "title": self.pulls[1].title,
                    "base_totals": None,
                    "head_totals": None,
                    "updatestamp": "2023-01-01T00:00:00Z",
                    "state": "open",
                    "ci_passed": None,
                    "author": None,
                },
                {
                    "pullid": self.pulls[0].pullid,
                    "title": self.pulls[0].title,
                    "base_totals": None,
                    "head_totals": None,
                    "updatestamp": "2022-01-01T00:00:00Z",
                    "state": "open",
                    "ci_passed": None,
                    "author": None,
                },
            ],
            "total_pages": 1,
        }

    def test_list_state(self):
        pull = PullFactory(repository=self.repo, state="closed")
        url = reverse(
            "api-v2-pulls-list",
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "repo_name": self.repo.name,
            },
        )
        res = self.client.get(f"{url}?state=closed")
        assert res.status_code == 200
        assert res.json() == {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "pullid": pull.pullid,
                    "title": pull.title,
                    "base_totals": None,
                    "head_totals": None,
                    "updatestamp": "2022-01-01T00:00:00Z",
                    "state": "closed",
                    "ci_passed": None,
                    "author": None,
                },
            ],
            "total_pages": 1,
        }

    def test_list_start_date(self):
        url = reverse(
            "api-v2-pulls-list",
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "repo_name": self.repo.name,
            },
        )
        res = self.client.get(f"{url}?start_date=2022-12-01")
        assert res.status_code == 200
        assert res.json() == {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "pullid": self.pulls[1].pullid,
                    "title": self.pulls[1].title,
                    "base_totals": None,
                    "head_totals": None,
                    "updatestamp": "2023-01-01T00:00:00Z",
                    "state": "open",
                    "ci_passed": None,
                    "author": None,
                },
            ],
            "total_pages": 1,
        }

    def test_list_cursor_pagination(self):
        url = reverse(
            "api-v2-pulls-list",
            kwargs={
                "service": self.org.service,
                "owner_username": self.org.username,
                "repo_name": self.repo.name,
            },
        )
        res = self.client.get(f"{url}?page_size=1&cursor=")
        assert res.status_code == 200
        data = res.json()
        assert data["results"] == [
            {
                "pullid": self.pulls[1].pullid,
                "title": self.pulls[1].title,
                "base_totals": None,
                "head_totals": None,
                "updatestamp": "2023-01-01T00:00:00Z",
                "state": "open",
                "ci_passed": None,
                "author": None,
            },
        ]
        assert data["previous"] is None
        assert data["next"] is not None

        res = self.client.get(data["next"])
        data = res.json()
        assert data["results"] == [
            {
                "pullid": self.pulls[0].pullid,
                "title": self.pulls[0].title,
                "base_totals": None,
                "head_totals": None,
                "updatestamp": "2022-01-01T00:00:00Z",
                "state": "open",
                "ci_passed": None,
                "author": None,
            },
        ]
        assert data["previous"] is not None
        assert data["next"] is None

    @patch("api.shared.repo.repository_accessors.RepoAccessors.get_repo_permissions")
    def test_retrieve(self, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)

        res = self.client.get(
            reverse(
                "api-v2-pulls-detail",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                    "pullid": self.pulls[0].pullid,
                },
            )
        )
        assert res.status_code == 200
        assert res.json() == {
            "pullid": self.pulls[0].pullid,
            "title": self.pulls[0].title,
            "base_totals": None,
            "head_totals": None,
            "updatestamp": "2022-01-01T00:00:00Z",
            "state": "open",
            "ci_passed": None,
            "author": None,
        }

    @patch("api.shared.permissions.RepositoryArtifactPermissions.has_permission")
    @patch("api.shared.permissions.SuperTokenPermissions.has_permission")
    def test_no_pull_if_unauthenticated_token_request(
        self,
        super_token_permissions_has_permission,
        repository_artifact_permisssions_has_permission,
    ):
        repository_artifact_permisssions_has_permission.return_value = False
        super_token_permissions_has_permission.return_value = False

        res = self.client.get(
            reverse(
                "api-v2-pulls-detail",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                    "pullid": self.pulls[0].pullid,
                },
            )
        )
        assert res.status_code == 403
        assert (
            res.data["detail"] == "You do not have permission to perform this action."
        )

    @override_settings(SUPER_API_TOKEN="testaxs3o76rdcdpfzexuccx3uatui2nw73r")
    @patch("api.shared.permissions.RepositoryArtifactPermissions.has_permission")
    def test_no_pull_if_not_super_token_nor_user_token(
        self, repository_artifact_permisssions_has_permission
    ):
        repository_artifact_permisssions_has_permission.return_value = False

        res = self.client.get(
            reverse(
                "api-v2-pulls-detail",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                    "pullid": self.pulls[0].pullid,
                },
            ),
            HTTP_AUTHORIZATION="Bearer 73c8d301-2e0b-42c0-9ace-95eef6b68e86",
        )
        assert res.status_code == 401
        assert res.data["detail"] == "Invalid token."

    @override_settings(SUPER_API_TOKEN="testaxs3o76rdcdpfzexuccx3uatui2nw73r")
    @patch("api.shared.permissions.RepositoryArtifactPermissions.has_permission")
    def test_no_pull_if_super_token_but_no_GET_request(
        self, repository_artifact_permisssions_has_permission
    ):
        repository_artifact_permisssions_has_permission.return_value = False
        res = self.client.post(
            reverse(
                "api-v2-pulls-detail",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                    "pullid": self.pulls[0].pullid,
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
    def test_pull_with_valid_super_token(
        self, repository_artifact_permisssions_has_permission
    ):
        repository_artifact_permisssions_has_permission.return_value = False
        res = self.client.get(
            reverse(
                "api-v2-pulls-detail",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                    "pullid": self.pulls[0].pullid,
                },
            ),
            HTTP_AUTHORIZATION="Bearer testaxs3o76rdcdpfzexuccx3uatui2nw73r",
        )
        assert res.status_code == 200
        assert res.json() == {
            "pullid": self.pulls[0].pullid,
            "title": self.pulls[0].title,
            "base_totals": None,
            "head_totals": None,
            "updatestamp": "2022-01-01T00:00:00Z",
            "state": "open",
            "ci_passed": None,
            "author": None,
        }
