from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from shared.reports.types import ReportTotals

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory


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


@patch("api.shared.repo.repository_accessors.RepoAccessors.get_repo_permissions")
class RepoCommitListTestCase(TestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov", service="github")
        self.repo = RepositoryFactory(author=self.org, name="test-repo", active=True)
        self.user = OwnerFactory(
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

    def test_commit_list_not_authenticated(self, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)

        author = OwnerFactory()
        repo = RepositoryFactory(author=author, private=False)
        commit = CommitFactory(repository=repo)

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

        self.client.force_login(user=self.user)
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
                    "timestamp": self.commit.timestamp.isoformat() + "Z",
                    "ci_passed": True,
                    "author": {
                        "service": "github",
                        "username": "codecov",
                        "name": self.org.name,
                    },
                    "branch": "master",
                    "totals": {
                        "files": 3,
                        "lines": 24,
                        "hits": 19,
                        "misses": 5,
                        "partials": 0,
                        "coverage": 79.17,
                        "branches": 0,
                        "methods": 0,
                        "sessions": 2,
                        "complexity": 2.0,
                        "complexity_total": 5.0,
                        "complexity_ratio": 40.0,
                        "diff": 0,
                    },
                    "state": "complete",
                }
            ],
        }

    def test_commit_list_null_coverage(self, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)

        self.commit.totals["c"] = None
        self.commit.save()

        self.client.force_login(user=self.user)
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
                    "timestamp": self.commit.timestamp.isoformat() + "Z",
                    "ci_passed": True,
                    "author": {
                        "service": "github",
                        "username": "codecov",
                        "name": self.org.name,
                    },
                    "branch": "master",
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
                }
            ],
        }


@patch("api.shared.repo.repository_accessors.RepoAccessors.get_repo_permissions")
class RepoCommitDetailTestCase(TestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov", service="github")
        self.repo = RepositoryFactory(author=self.org, name="test-repo", active=True)
        self.user = OwnerFactory(
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

    @patch("core.models.ReportService.build_report_from_commit")
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

    @patch("core.models.ReportService.build_report_from_commit")
    def test_commit_detail_authenticated(
        self, build_report_from_commit, get_repo_permissions
    ):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.return_value = MockReport()

        self.client.force_login(user=self.user)
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
            "timestamp": self.commit.timestamp.isoformat() + "Z",
            "ci_passed": True,
            "author": {
                "service": "github",
                "username": "codecov",
                "name": self.org.name,
            },
            "branch": "master",
            "totals": {
                "files": 3,
                "lines": 24,
                "hits": 19,
                "misses": 5,
                "partials": 0,
                "coverage": 79.17,
                "branches": 0,
                "methods": 0,
                "sessions": 2,
                "complexity": 2.0,
                "complexity_total": 5.0,
                "complexity_ratio": 40.0,
                "diff": 0,
            },
            "state": "complete",
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
