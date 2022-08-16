from unittest.mock import patch

from django.test import TestCase
from rest_framework.reverse import reverse
from shared.reports.resources import Report, ReportFile, ReportLine
from shared.utils.sessions import Session

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import BranchFactory, CommitFactory, RepositoryFactory


def sample_report():
    report = Report()
    first_file = ReportFile("foo/file1.py")
    first_file.append(
        1, ReportLine.create(coverage=1, sessions=[[0, 1]], complexity=(10, 2))
    )
    first_file.append(2, ReportLine.create(coverage=0, sessions=[[0, 1]]))
    first_file.append(3, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    first_file.append(5, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    first_file.append(6, ReportLine.create(coverage=0, sessions=[[0, 1]]))
    first_file.append(8, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    first_file.append(9, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    first_file.append(10, ReportLine.create(coverage=0, sessions=[[0, 1]]))
    second_file = ReportFile("bar/file2.py")
    second_file.append(12, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    second_file.append(
        51, ReportLine.create(coverage="1/2", type="b", sessions=[[0, 1]])
    )
    report.append(first_file)
    report.append(second_file)
    report.add_session(Session(flags=["flag1", "flag2"]))
    return report


@patch("api.shared.repo.repository_accessors.RepoAccessors.get_repo_permissions")
class ReportViewSetTestCase(TestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov", service="github")
        self.repo = RepositoryFactory(author=self.org, name="test-repo", active=True)
        self.user = OwnerFactory(
            username="codecov-user",
            service="github",
            organizations=[self.org.ownerid],
            permission=[self.repo.repoid],
        )
        self.commit1 = CommitFactory(
            author=self.org,
            repository=self.repo,
        )
        self.commit2 = CommitFactory(
            author=self.org,
            repository=self.repo,
        )
        self.branch = BranchFactory(repository=self.repo, name="test-branch")
        self.commit3 = CommitFactory(
            author=self.org,
            repository=self.repo,
            branch=self.branch,
        )
        self.branch.head = self.commit3.commitid
        self.branch.save()

    def _request_report(self, **params):
        self.client.force_login(user=self.user)
        url = reverse(
            "report-detail",
            kwargs={
                "service": "github",
                "owner_username": self.org.username,
                "repo_name": self.repo.name,
            },
        )
        if "sha" in params:
            sha = params["sha"]
            url += f"?sha={sha}"
        elif "branch" in params:
            branch = params["branch"]
            url += f"?branch={branch}"
        elif "path" in params:
            path = params["path"]
            url += f"?path={path}"
        return self.client.get(url)

    @patch("services.archive.ReportService.build_report_from_commit")
    def test_report(self, build_report_from_commit, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.return_value = sample_report()

        res = self._request_report()
        assert res.status_code == 200
        assert res.json() == {
            "totals": {
                "files": 2,
                "lines": 10,
                "hits": 6,
                "misses": 3,
                "partials": 1,
                "coverage": 60.0,
                "branches": 1,
                "methods": 0,
                "messages": 0,
                "sessions": 1,
                "complexity": 10.0,
                "complexity_total": 2.0,
                "complexity_ratio": 500.0,
                "diff": 0,
            },
            "files": [
                {
                    "name": "foo/file1.py",
                    "totals": {
                        "files": 0,
                        "lines": 8,
                        "hits": 5,
                        "misses": 3,
                        "partials": 0,
                        "coverage": 62.5,
                        "branches": 0,
                        "methods": 0,
                        "messages": 0,
                        "sessions": 0,
                        "complexity": 10.0,
                        "complexity_total": 2.0,
                        "complexity_ratio": 500.0,
                        "diff": 0,
                    },
                    "line_coverage": [
                        [1, 0],
                        [2, 1],
                        [3, 0],
                        [5, 0],
                        [6, 1],
                        [8, 0],
                        [9, 0],
                        [10, 1],
                    ],
                },
                {
                    "name": "bar/file2.py",
                    "totals": {
                        "files": 0,
                        "lines": 2,
                        "hits": 1,
                        "misses": 0,
                        "partials": 1,
                        "coverage": 50.0,
                        "branches": 1,
                        "methods": 0,
                        "messages": 0,
                        "sessions": 0,
                        "complexity": 0.0,
                        "complexity_total": 0.0,
                        "complexity_ratio": 0,
                        "diff": 0,
                    },
                    "line_coverage": [[12, 0], [51, 2]],
                },
            ],
        }

        build_report_from_commit.assert_called_once_with(self.commit1)

    @patch("services.archive.ReportService.build_report_from_commit")
    def test_report_commit_sha(self, build_report_from_commit, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.return_value = sample_report()

        res = self._request_report(sha=self.commit2.commitid)
        assert res.status_code == 200
        assert res.json() == {
            "totals": {
                "files": 2,
                "lines": 10,
                "hits": 6,
                "misses": 3,
                "partials": 1,
                "coverage": 60.0,
                "branches": 1,
                "methods": 0,
                "messages": 0,
                "sessions": 1,
                "complexity": 10.0,
                "complexity_total": 2.0,
                "complexity_ratio": 500.0,
                "diff": 0,
            },
            "files": [
                {
                    "name": "foo/file1.py",
                    "totals": {
                        "files": 0,
                        "lines": 8,
                        "hits": 5,
                        "misses": 3,
                        "partials": 0,
                        "coverage": 62.5,
                        "branches": 0,
                        "methods": 0,
                        "messages": 0,
                        "sessions": 0,
                        "complexity": 10.0,
                        "complexity_total": 2.0,
                        "complexity_ratio": 500.0,
                        "diff": 0,
                    },
                    "line_coverage": [
                        [1, 0],
                        [2, 1],
                        [3, 0],
                        [5, 0],
                        [6, 1],
                        [8, 0],
                        [9, 0],
                        [10, 1],
                    ],
                },
                {
                    "name": "bar/file2.py",
                    "totals": {
                        "files": 0,
                        "lines": 2,
                        "hits": 1,
                        "misses": 0,
                        "partials": 1,
                        "coverage": 50.0,
                        "branches": 1,
                        "methods": 0,
                        "messages": 0,
                        "sessions": 0,
                        "complexity": 0.0,
                        "complexity_total": 0.0,
                        "complexity_ratio": 0,
                        "diff": 0,
                    },
                    "line_coverage": [[12, 0], [51, 2]],
                },
            ],
        }

        build_report_from_commit.assert_called_once_with(self.commit2)

    @patch("services.archive.ReportService.build_report_from_commit")
    def test_report_branch(self, build_report_from_commit, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.return_value = sample_report()

        res = self._request_report(branch="test-branch")
        assert res.status_code == 200
        assert res.json() == {
            "totals": {
                "files": 2,
                "lines": 10,
                "hits": 6,
                "misses": 3,
                "partials": 1,
                "coverage": 60.0,
                "branches": 1,
                "methods": 0,
                "messages": 0,
                "sessions": 1,
                "complexity": 10.0,
                "complexity_total": 2.0,
                "complexity_ratio": 500.0,
                "diff": 0,
            },
            "files": [
                {
                    "name": "foo/file1.py",
                    "totals": {
                        "files": 0,
                        "lines": 8,
                        "hits": 5,
                        "misses": 3,
                        "partials": 0,
                        "coverage": 62.5,
                        "branches": 0,
                        "methods": 0,
                        "messages": 0,
                        "sessions": 0,
                        "complexity": 10.0,
                        "complexity_total": 2.0,
                        "complexity_ratio": 500.0,
                        "diff": 0,
                    },
                    "line_coverage": [
                        [1, 0],
                        [2, 1],
                        [3, 0],
                        [5, 0],
                        [6, 1],
                        [8, 0],
                        [9, 0],
                        [10, 1],
                    ],
                },
                {
                    "name": "bar/file2.py",
                    "totals": {
                        "files": 0,
                        "lines": 2,
                        "hits": 1,
                        "misses": 0,
                        "partials": 1,
                        "coverage": 50.0,
                        "branches": 1,
                        "methods": 0,
                        "messages": 0,
                        "sessions": 0,
                        "complexity": 0.0,
                        "complexity_total": 0.0,
                        "complexity_ratio": 0,
                        "diff": 0,
                    },
                    "line_coverage": [[12, 0], [51, 2]],
                },
            ],
        }

        build_report_from_commit.assert_called_once_with(self.commit3)

    @patch("services.archive.ReportService.build_report_from_commit")
    def test_report_path(self, build_report_from_commit, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.return_value = sample_report()

        res = self._request_report(path="bar")
        assert res.status_code == 200
        assert res.json() == {
            "totals": {
                "files": 1,
                "lines": 2,
                "hits": 1,
                "misses": 0,
                "partials": 1,
                "coverage": 50.0,
                "branches": 1,
                "methods": 0,
                "messages": 0,
                "sessions": 1,
                "complexity": 0.0,
                "complexity_total": 0.0,
                "complexity_ratio": 0,
                "diff": 0,
            },
            "files": [
                {
                    "name": "bar/file2.py",
                    "totals": {
                        "files": 0,
                        "lines": 2,
                        "hits": 1,
                        "misses": 0,
                        "partials": 1,
                        "coverage": 50.0,
                        "branches": 1,
                        "methods": 0,
                        "messages": 0,
                        "sessions": 0,
                        "complexity": 0.0,
                        "complexity_total": 0.0,
                        "complexity_ratio": 0,
                        "diff": 0,
                    },
                    "line_coverage": [[12, 0], [51, 2]],
                }
            ],
        }

        build_report_from_commit.assert_called_once_with(self.commit1)
