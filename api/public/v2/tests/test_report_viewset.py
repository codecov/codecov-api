import os
from unittest.mock import call, patch
from urllib.parse import urlencode

from django.test import TestCase, override_settings
from rest_framework.reverse import reverse
from shared.reports.resources import Report, ReportFile, ReportLine
from shared.utils.sessions import Session

from codecov_auth.models import UserToken
from codecov_auth.tests.factories import OwnerFactory, UserTokenFactory
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


def flags_report():
    report = Report()
    session_a_id, _ = report.add_session(Session(flags=["flag-a"]))
    session_b_id, _ = report.add_session(Session(flags=["flag-b"]))

    file_a = ReportFile("foo/file1.py")
    file_a.append(1, ReportLine.create(coverage=1, sessions=[[session_a_id, 1]]))
    file_a.append(2, ReportLine.create(coverage=0, sessions=[[session_a_id, 0]]))
    file_a.append(3, ReportLine.create(coverage=1, sessions=[[session_a_id, 1]]))
    file_a.append(5, ReportLine.create(coverage=1, sessions=[[session_a_id, 1]]))
    file_a.append(6, ReportLine.create(coverage=0, sessions=[[session_a_id, 0]]))
    file_a.append(8, ReportLine.create(coverage=1, sessions=[[session_a_id, 1]]))
    file_a.append(9, ReportLine.create(coverage=1, sessions=[[session_a_id, 1]]))
    file_a.append(10, ReportLine.create(coverage=0, sessions=[[session_a_id, 0]]))
    report.append(file_a)

    file_b = ReportFile("bar/file2.py")
    file_b.append(12, ReportLine.create(coverage=1, sessions=[[session_b_id, 1]]))
    file_b.append(
        51, ReportLine.create(coverage="1/2", type="b", sessions=[[session_b_id, 2]])
    )
    report.append(file_b)

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

    def _request_report(self, user_token=None, **params):
        self.client.force_login(user=self.user)
        url = reverse(
            "report-detail",
            kwargs={
                "service": "github",
                "owner_username": self.org.username,
                "repo_name": self.repo.name,
            },
        )

        qs = urlencode(params)
        url = f"{url}?{qs}"
        return (
            self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {user_token}")
            if user_token
            else self.client.get(url)
        )

    def _post_report(self, user_token=None, **params):
        self.client.force_login(user=self.user)
        url = reverse(
            "report-detail",
            kwargs={
                "service": "github",
                "owner_username": self.org.username,
                "repo_name": self.repo.name,
            },
        )

        qs = urlencode(params)
        url = f"{url}?{qs}"
        return (
            self.client.post(url, HTTP_AUTHORIZATION=f"Bearer {user_token}")
            if user_token
            else self.client.post(url)
        )

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
    def test_report_nonexistent_commit_sha(
        self, build_report_from_commit, get_repo_permissions
    ):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.return_value = sample_report()

        sha = "aSD*FAJ#GVUAJS-random-sha"
        res = self._request_report(sha=sha)
        assert res.status_code == 404
        assert res.json() == {
            "detail": f"The commit {sha} is not in our records. Please specify valid commit."
        }

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
    def test_report_nonexistent_branch(
        self, build_report_from_commit, get_repo_permissions
    ):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.return_value = sample_report()

        branch = "random-nonexistent-branch-aaa"
        res = self._request_report(branch=branch)
        assert res.status_code == 404
        assert res.json() == {
            "detail": f"The branch '{branch}' in not in our records. Please provide a valid branch name."
        }

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

    @patch("services.archive.ReportService.build_report_from_commit")
    def test_report_invalid_path(self, build_report_from_commit, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.return_value = sample_report()
        path = "random-path-that-doesnt-exist-1234"

        res = self._request_report(path=path)
        assert res.status_code == 404
        assert res.json() == {
            "detail": f"The file path '{path}' does not exist. Please provide an existing file path."
        }

        build_report_from_commit.assert_called_once_with(self.commit1)

    @patch("services.archive.ReportService.build_report_from_commit")
    def test_report_flag(self, build_report_from_commit, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.return_value = flags_report()

        res = self._request_report(flag="flag-a")
        assert res.status_code == 200
        assert res.json() == {
            "totals": {
                "files": 1,
                "lines": 8,
                "hits": 5,
                "misses": 3,
                "partials": 0,
                "coverage": 62.5,
                "branches": 0,
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
                        "complexity": 0.0,
                        "complexity_total": 0.0,
                        "complexity_ratio": 0,
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
                        "lines": 0,
                        "hits": 0,
                        "misses": 0,
                        "partials": 0,
                        "coverage": 0,
                        "branches": 0,
                        "methods": 0,
                        "messages": 0,
                        "sessions": 0,
                        "complexity": 0.0,
                        "complexity_total": 0.0,
                        "complexity_ratio": 0,
                        "diff": 0,
                    },
                    "line_coverage": [],
                },
            ],
        }

        build_report_from_commit.assert_called_once_with(self.commit1)

        res = self._request_report(flag="flag-b")
        assert res.status_code == 200
        assert res.json() == {
            "totals": {
                "files": 1,
                "lines": 2,
                "hits": 2,
                "misses": 0,
                "partials": 0,
                "coverage": 100.0,
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
                    "name": "foo/file1.py",
                    "totals": {
                        "files": 0,
                        "lines": 0,
                        "hits": 0,
                        "misses": 0,
                        "partials": 0,
                        "coverage": 0,
                        "branches": 0,
                        "methods": 0,
                        "messages": 0,
                        "sessions": 0,
                        "complexity": 0.0,
                        "complexity_total": 0.0,
                        "complexity_ratio": 0,
                        "diff": 0,
                    },
                    "line_coverage": [],
                },
                {
                    "name": "bar/file2.py",
                    "totals": {
                        "files": 0,
                        "lines": 2,
                        "hits": 2,
                        "misses": 0,
                        "partials": 0,
                        "coverage": 100.0,
                        "branches": 1,
                        "methods": 0,
                        "messages": 0,
                        "sessions": 0,
                        "complexity": 0.0,
                        "complexity_total": 0.0,
                        "complexity_ratio": 0,
                        "diff": 0,
                    },
                    "line_coverage": [[12, 0], [51, 0]],
                },
            ],
        }

        build_report_from_commit.assert_has_calls(
            [call(self.commit1), call(self.commit1)]
        )

    @patch("api.shared.permissions.RepositoryArtifactPermissions.has_permission")
    @patch("api.shared.permissions.SuperTokenPermissions.has_permission")
    def test_no_report_if_unauthenticated_token_request(
        self,
        super_token_permissions_has_permission,
        repository_artifact_permisssions_has_permission,
        _,
    ):
        super_token_permissions_has_permission.return_value = False
        repository_artifact_permisssions_has_permission.return_value = False

        res = self._request_report()
        assert res.status_code == 403
        assert (
            res.data["detail"] == "You do not have permission to perform this action."
        )

    @override_settings(SUPER_API_TOKEN="testaxs3o76rdcdpfzexuccx3uatui2nw73r")
    @patch("api.shared.permissions.RepositoryArtifactPermissions.has_permission")
    def test_no_report_if_not_super_token_nor_user_token(
        self, repository_artifact_permisssions_has_permission, _
    ):
        repository_artifact_permisssions_has_permission.return_value = False
        res = self._request_report("73c8d301-2e0b-42c0-9ace-95eef6b68e86")
        assert res.status_code == 401
        assert res.data["detail"] == "Invalid token."

    @override_settings(SUPER_API_TOKEN="testaxs3o76rdcdpfzexuccx3uatui2nw73r")
    @patch("api.shared.permissions.RepositoryArtifactPermissions.has_permission")
    def test_no_report_if_super_token_but_no_GET_request(
        self, repository_artifact_permisssions_has_permission, _
    ):
        repository_artifact_permisssions_has_permission.return_value = False
        res = self._post_report("testaxs3o76rdcdpfzexuccx3uatui2nw73r")
        assert res.status_code == 403
        assert (
            res.data["detail"] == "You do not have permission to perform this action."
        )

    @override_settings(SUPER_API_TOKEN="testaxs3o76rdcdpfzexuccx3uatui2nw73r")
    @patch("services.archive.ReportService.build_report_from_commit")
    def test_report_super_token_permission_success(
        self,
        build_report_from_commit,
        _,
    ):
        build_report_from_commit.return_value = sample_report()
        res = self._request_report("testaxs3o76rdcdpfzexuccx3uatui2nw73r")
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

    @override_settings(SUPER_API_TOKEN="testaxs3o76rdcdpfzexuccx3uatui2nw73r")
    @patch("api.shared.permissions.RepositoryPermissionsService.user_is_activated")
    @patch("services.archive.ReportService.build_report_from_commit")
    def test_report_success_if_token_is_not_super_but_is_user_token(
        self, build_report_from_commit, mock_is_user_activated, get_repo_permissions
    ):
        build_report_from_commit.return_value = sample_report()
        mock_is_user_activated.return_value = True
        get_repo_permissions.return_value = (True, True)
        user_token = UserTokenFactory(
            owner=self.user,
        )
        res = self._request_report(user_token.token)
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
