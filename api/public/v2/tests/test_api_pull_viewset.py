from unittest.mock import MagicMock, patch

from django.test import override_settings
from django.urls import reverse
from freezegun import freeze_time
from shared.django_apps.core.tests.factories import (
    OwnerFactory,
    PullFactory,
    RepositoryFactory,
)

from codecov.tests.base_test import InternalAPITest
from core.models import Pull
from utils.test_utils import APIClient


@freeze_time("2022-01-01T00:00:00")
class PullViewsetTests(InternalAPITest):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org)
        self.current_owner = OwnerFactory(
            permission=[self.repo.repoid],
            organizations=[self.org.ownerid],
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
        self.no_patch_response = dict(hits=0, misses=0, partials=0, coverage=0.0)

    @patch("api.public.v2.pull.serializers.PullSerializer.get_patch")
    def test_list(self, mock_patch):
        mock_patch.return_value = self.no_patch_response
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
                    "patch": {"hits": 0, "misses": 0, "partials": 0, "coverage": 0.0},
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
                    "patch": {"hits": 0, "misses": 0, "partials": 0, "coverage": 0.0},
                },
            ],
            "total_pages": 1,
        }

    @patch("api.public.v2.pull.serializers.PullSerializer.get_patch")
    def test_list_state(self, mock_patch):
        mock_patch.return_value = self.no_patch_response
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
                    "patch": {"hits": 0, "misses": 0, "partials": 0, "coverage": 0.0},
                }
            ],
            "total_pages": 1,
        }

    @patch("api.public.v2.pull.serializers.PullSerializer.get_patch")
    def test_list_start_date(self, mock_patch):
        mock_patch.return_value = self.no_patch_response
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
                    "patch": {"hits": 0, "misses": 0, "partials": 0, "coverage": 0.0},
                }
            ],
            "total_pages": 1,
        }

    @patch("api.public.v2.pull.serializers.PullSerializer.get_patch")
    def test_list_cursor_pagination(self, mock_patch):
        mock_patch.return_value = self.no_patch_response
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
                "patch": {"hits": 0, "misses": 0, "partials": 0, "coverage": 0.0},
            }
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
                "patch": {"hits": 0, "misses": 0, "partials": 0, "coverage": 0.0},
            }
        ]
        assert data["previous"] is not None
        assert data["next"] is None

    @patch("api.public.v2.pull.serializers.PullSerializer.get_patch")
    @patch("api.shared.repo.repository_accessors.RepoAccessors.get_repo_permissions")
    def test_retrieve(self, get_repo_permissions, mock_patch):
        mock_patch.return_value = self.no_patch_response
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
            "patch": {"hits": 0, "misses": 0, "partials": 0, "coverage": 0.0},
        }

    @patch("api.shared.permissions.RepositoryArtifactPermissions.has_permission")
    @patch("api.shared.permissions.SuperTokenPermissions.has_permission")
    def test_no_pull_if_unauthenticated_token_request(
        self,
        super_token_permissions_has_permission,
        repository_artifact_permissions_has_permission,
    ):
        repository_artifact_permissions_has_permission.return_value = False
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
        self, repository_artifact_permissions_has_permission
    ):
        repository_artifact_permissions_has_permission.return_value = False
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
        self, repository_artifact_permissions_has_permission
    ):
        repository_artifact_permissions_has_permission.return_value = False
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
    @patch("api.public.v2.pull.serializers.PullSerializer.get_patch")
    def test_pull_with_valid_super_token(self, mock_patch):
        mock_patch.return_value = self.no_patch_response
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
            "patch": {"hits": 0, "misses": 0, "partials": 0, "coverage": 0.0},
        }

    @patch("api.public.v2.pull.serializers.ComparisonReport")
    @patch("services.comparison.CommitComparison.objects.filter")
    def test_retrieve_with_patch_coverage(self, mock_cc_filter, mock_comparison_report):
        mock_cc_instance = MagicMock(is_processed=True)
        mock_cc_filter.return_value.select_related.return_value.first.return_value = (
            mock_cc_instance
        )

        mock_file = MagicMock()
        mock_file.patch_coverage.hits = 10
        mock_file.patch_coverage.misses = 5
        mock_file.patch_coverage.partials = 2
        mock_comparison_report.return_value.impacted_files = [mock_file]

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
        data = res.json()
        assert data["patch"] == {
            "hits": 10,
            "misses": 5,
            "partials": 2,
            "coverage": 58.82,
        }

    @patch("api.public.v2.pull.serializers.ComparisonReport")
    @patch("services.comparison.CommitComparison.objects.filter")
    def test_retrieve_with_patch_coverage_no_branches(
        self, mock_cc_filter, mock_comparison_report
    ):
        mock_cc_instance = MagicMock(is_processed=True)
        mock_cc_filter.return_value.select_related.return_value.first.return_value = (
            mock_cc_instance
        )

        mock_file = MagicMock()
        mock_file.patch_coverage.hits = 0
        mock_file.patch_coverage.misses = 0
        mock_file.patch_coverage.partials = 0
        mock_comparison_report.return_value.impacted_files = [mock_file]

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
        data = res.json()
        assert data["patch"] == self.no_patch_response

    @patch("api.public.v2.pull.serializers.ComparisonReport")
    @patch("services.comparison.CommitComparison.objects.filter")
    def test_retrieve_with_patch_coverage_no_commit_comparison(
        self, mock_cc_filter, mock_comparison_report
    ):
        mock_cc_instance = MagicMock(is_processed=False)
        mock_cc_filter.return_value.select_related.return_value.first.return_value = (
            mock_cc_instance
        )

        mock_file = MagicMock()
        mock_file.patch_coverage.hits = 0
        mock_file.patch_coverage.misses = 0
        mock_file.patch_coverage.partials = 0
        mock_comparison_report.return_value.impacted_files = [mock_file]

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
        data = res.json()
        assert data["patch"] is None
