from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    CommitWithReportFactory,
    OwnerFactory,
    RepositoryFactory,
)
from shared.reports.types import ReportTotals

from utils.test_utils import APIClient


class MockCoverage(object):
    def __init__(self, cov):
        self.coverage = cov


class MockReportFile(object):
    def __init__(self, name):
        self.name = name
        self.lines = [
            [1, MockCoverage("1/2")],  # partial => 2
            [2, MockCoverage(1)],  # hit => 0
            [3, MockCoverage(0)],  # miss => 1
        ]
        self.totals = ReportTotals(
            lines=3,
            hits=1,
            misses=1,
            partials=1,
            coverage=33.33,
        )


class MockReport(object):
    def __init__(self):
        self.files = ["foo/a.py", "bar/b.py"]
        self.totals = ReportTotals(
            files=2,
            lines=6,
            hits=2,
            misses=2,
            partials=2,
            coverage=33.33,
        )

    def get(self, name):
        return MockReportFile(name)


class BaseRepoCommitTestCase(TestCase):
    def setUp(self) -> None:
        self.org = OwnerFactory(username="codecov", service="github")
        self.repo = RepositoryFactory(author=self.org, name="test-repo", active=True)
        self.current_owner = OwnerFactory(
            username="codecov-user",
            service="github",
            organizations=[self.org.ownerid],
            permission=[self.repo.repoid],
        )
        self.commit = CommitFactory(
            author=self.org,
            repository=self.repo,
            totals={
                "C": 2,
                "M": 0,
                "N": 5,
                "b": 0,
                "c": "79.16667",
                "d": 0,
                "f": 3,
                "h": 19,
                "m": 5,
                "n": 24,
                "p": 0,
                "s": 2,
                "diff": 0,
            },
        )
        self.client = APIClient()
        self.client.force_login_owner(self.current_owner)


@patch("api.shared.repo.repository_accessors.RepoAccessors.get_repo_permissions")
class RepoCommitListTestCase(BaseRepoCommitTestCase):
    def test_commit_list_not_authenticated(self, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)

        author = OwnerFactory()
        repo = RepositoryFactory(author=author, private=False)
        CommitFactory(repository=repo)

        self.client.logout()
        response = self.client.get(
            reverse(
                "api-v2-commits-list",
                kwargs={
                    "service": author.service,
                    "owner_username": author.username,
                    "repo_name": repo.name,
                },
            )
        )

        # allows access to public repos
        assert response.status_code == 200

    def test_commit_list_authenticated(self, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)

        response = self.client.get(
            reverse(
                "api-v2-commits-list",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                },
            )
        )
        assert response.status_code == 200
        assert response.json() == {
            "count": 1,
            "total_pages": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "commitid": self.commit.commitid,
                    "message": self.commit.message,
                    "timestamp": self.commit.timestamp.replace(tzinfo=None).isoformat()
                    + "Z",
                    "ci_passed": True,
                    "author": {
                        "service": "github",
                        "username": "codecov",
                        "name": self.org.name,
                    },
                    "branch": "main",
                    "totals": {
                        "files": 3,
                        "lines": 24,
                        "hits": 19,
                        "misses": 5,
                        "partials": 0,
                        "coverage": 79.16,
                        "branches": 0,
                        "methods": 0,
                        "sessions": 2,
                        "complexity": 2.0,
                        "complexity_total": 5.0,
                        "complexity_ratio": 40.0,
                        "diff": 0,
                    },
                    "state": "complete",
                    "parent": self.commit.parent_commit_id,
                }
            ],
        }

    def test_commit_list_null_coverage(self, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)

        self.commit.totals["c"] = None
        self.commit.save()

        response = self.client.get(
            reverse(
                "api-v2-commits-list",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                },
            )
        )
        assert response.status_code == 200
        assert response.json() == {
            "count": 1,
            "total_pages": 1,
            "next": None,
            "previous": None,
            "results": [
                {
                    "commitid": self.commit.commitid,
                    "message": self.commit.message,
                    "timestamp": self.commit.timestamp.replace(tzinfo=None).isoformat()
                    + "Z",
                    "ci_passed": True,
                    "author": {
                        "service": "github",
                        "username": "codecov",
                        "name": self.org.name,
                    },
                    "branch": "main",
                    "totals": {
                        "files": 3,
                        "lines": 24,
                        "hits": 19,
                        "misses": 5,
                        "partials": 0,
                        "coverage": None,
                        "branches": 0,
                        "methods": 0,
                        "sessions": 2,
                        "complexity": 2.0,
                        "complexity_total": 5.0,
                        "complexity_ratio": 40.0,
                        "diff": 0,
                    },
                    "state": "complete",
                    "parent": self.commit.parent_commit_id,
                }
            ],
        }


@patch("api.shared.repo.repository_accessors.RepoAccessors.get_repo_permissions")
class RepoCommitDetailTestCase(BaseRepoCommitTestCase):
    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_commit_detail_not_authenticated(
        self, build_report_from_commit, get_repo_permissions
    ):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.return_value = MockReport()

        author = OwnerFactory()
        repo = RepositoryFactory(author=author, private=False)
        commit = CommitFactory(author=author, repository=repo)

        self.client.logout()
        response = self.client.get(
            reverse(
                "api-v2-commits-detail",
                kwargs={
                    "service": author.service,
                    "owner_username": author.username,
                    "repo_name": repo.name,
                    "commitid": commit.commitid,
                },
            )
        )
        # allows access to public repos
        assert response.status_code == 200

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_commit_detail_authenticated(
        self, build_report_from_commit, get_repo_permissions
    ):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.return_value = MockReport()

        response = self.client.get(
            reverse(
                "api-v2-commits-detail",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                    "commitid": self.commit.commitid,
                },
            )
        )
        assert response.status_code == 200
        assert response.json() == {
            "commitid": self.commit.commitid,
            "message": self.commit.message,
            "timestamp": self.commit.timestamp.replace(tzinfo=None).isoformat() + "Z",
            "ci_passed": True,
            "author": {
                "service": "github",
                "username": "codecov",
                "name": self.org.name,
            },
            "branch": "main",
            "totals": {
                "files": 3,
                "lines": 24,
                "hits": 19,
                "misses": 5,
                "partials": 0,
                "coverage": 79.16,
                "branches": 0,
                "methods": 0,
                "sessions": 2,
                "complexity": 2.0,
                "complexity_total": 5.0,
                "complexity_ratio": 40.0,
                "diff": 0,
            },
            "state": "complete",
            "parent": self.commit.parent_commit_id,
            "report": {
                "files": [
                    {
                        "name": "foo/a.py",
                        "totals": {
                            "files": 0,
                            "lines": 3,
                            "hits": 1,
                            "misses": 1,
                            "partials": 1,
                            "coverage": 33.33,
                            "branches": 0,
                            "methods": 0,
                            "messages": 0,
                            "sessions": 0,
                            "complexity": 0.0,
                            "complexity_total": 0.0,
                            "complexity_ratio": 0,
                            "diff": 0,
                        },
                        "line_coverage": [
                            [1, 2],
                            [2, 0],
                            [3, 1],
                        ],
                    },
                    {
                        "name": "bar/b.py",
                        "totals": {
                            "files": 0,
                            "lines": 3,
                            "hits": 1,
                            "misses": 1,
                            "partials": 1,
                            "coverage": 33.33,
                            "branches": 0,
                            "methods": 0,
                            "messages": 0,
                            "sessions": 0,
                            "complexity": 0.0,
                            "complexity_total": 0.0,
                            "complexity_ratio": 0,
                            "diff": 0,
                        },
                        "line_coverage": [
                            [1, 2],
                            [2, 0],
                            [3, 1],
                        ],
                    },
                ],
                "totals": {
                    "files": 2,
                    "lines": 6,
                    "hits": 2,
                    "misses": 2,
                    "partials": 2,
                    "coverage": 33.33,
                    "branches": 0,
                    "methods": 0,
                    "messages": 0,
                    "sessions": 0,
                    "complexity": 0.0,
                    "complexity_total": 0.0,
                    "complexity_ratio": 0,
                    "diff": 0,
                },
            },
        }


@patch("api.shared.repo.repository_accessors.RepoAccessors.get_repo_permissions")
class RepoCommitUploadsTestCase(BaseRepoCommitTestCase):
    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_commit_uploads_not_authenticated(
        self, build_report_from_commit, get_repo_permissions
    ):
        build_report_from_commit.return_value = MockReport()
        get_repo_permissions.return_value = (True, True)

        author = OwnerFactory()
        repo_public = RepositoryFactory(author=author, private=False)
        repo_private = RepositoryFactory(author=author, private=True)
        commit_public = CommitWithReportFactory(author=author, repository=repo_public)
        commit_private = CommitWithReportFactory(author=author, repository=repo_private)

        self.client.logout()
        response = self.client.get(
            reverse(
                "api-v2-commits-detail",
                kwargs={
                    "service": author.service,
                    "owner_username": author.username,
                    "repo_name": repo_public.name,
                    "commitid": commit_public.commitid,
                },
            )
        )

        # allows access to public repos
        assert response.status_code == 200

        response = self.client.get(
            reverse(
                "api-v2-commits-detail",
                kwargs={
                    "service": author.service,
                    "owner_username": author.username,
                    "repo_name": repo_private.name,
                    "commitid": commit_private.commitid,
                },
            )
        )

        # does not allow access to private repos
        assert response.status_code == 404

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_commit_uploads_authenticated(
        self, build_report_from_commit, get_repo_permissions
    ):
        build_report_from_commit.return_value = MockReport()
        get_repo_permissions.return_value = (True, True)
        commit = CommitWithReportFactory(author=self.org, repository=self.repo)

        response = self.client.get(
            reverse(
                "api-v2-commits-uploads",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                    "commitid": commit.commitid,
                },
            )
        )
        data = response.json()

        expected_storage_path = "v4/raw/2019-01-10/4434BC2A2EC4FCA57F77B473D83F928C/abf6d4df662c47e32460020ab14abf9303581429/9ccc55a1-8b41-4bb1-a946-ee7a33a7fb56.txt"

        assert response.status_code == 200
        assert len(data["results"]) == 2
        assert data["results"][0]["storage_path"] == expected_storage_path
        assert data["results"][1]["storage_path"] == expected_storage_path
        assert data["results"][0]["totals"] == {
            "files": 3,
            "lines": 20,
            "hits": 17,
            "misses": 3,
            "partials": 0,
            "coverage": 85.0,
            "branches": 0,
            "methods": 0,
        }
        assert data["results"][1]["totals"] == {
            "files": 3,
            "lines": 20,
            "hits": 17,
            "misses": 3,
            "partials": 0,
            "coverage": 85.0,
            "branches": 0,
            "methods": 0,
        }

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_commit_uploads_pagination(
        self, build_report_from_commit, get_repo_permissions
    ):
        build_report_from_commit.return_value = MockReport()
        get_repo_permissions.return_value = (True, True)
        commit = CommitWithReportFactory(author=self.org, repository=self.repo)

        response = self.client.get(
            reverse(
                "api-v2-commits-uploads",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                    "commitid": commit.commitid,
                },
            ),
            data={"page_size": 1, "page": 1},
        )
        data_1 = response.json()
        # Check that first page has one item
        assert response.status_code == 200
        assert data_1["total_pages"] == 2
        assert data_1["count"] == 2
        assert len(data_1["results"]) == 1

        response = self.client.get(
            reverse(
                "api-v2-commits-uploads",
                kwargs={
                    "service": self.org.service,
                    "owner_username": self.org.username,
                    "repo_name": self.repo.name,
                    "commitid": commit.commitid,
                },
            ),
            data={"page_size": 1, "page": 2},
        )
        data_2 = response.json()
        # Check that second page has one item
        assert response.status_code == 200
        assert data_2["total_pages"] == 2
        assert data_2["count"] == 2
        assert len(data_2["results"]) == 1

        # Check that first and second items are different
        assert data_1["results"][0]["created_at"] != data_2["results"][0]["created_at"]
