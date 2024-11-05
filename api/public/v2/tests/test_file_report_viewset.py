from unittest.mock import call, patch
from urllib.parse import urlencode

from django.conf import settings
from django.test import TestCase
from rest_framework.reverse import reverse
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    RepositoryFactory,
)
from shared.reports.resources import Report, ReportFile, ReportLine
from shared.utils.sessions import Session

from core.models import Branch
from utils.test_utils import APIClient


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
class FileReportViewSetTestCase(TestCase):
    def setUp(self):
        self.service = "github"
        self.username = "codecov"
        self.repo_name = "test-repo"
        self.org = OwnerFactory(username=self.username, service=self.service)
        self.repo = RepositoryFactory(author=self.org, name=self.repo_name, active=True)
        self.current_owner = OwnerFactory(
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
            parent_commit_id=self.commit1.commitid,
        )
        self.commit3 = CommitFactory(
            author=self.org,
            repository=self.repo,
            parent_commit_id=self.commit2.commitid,
        )
        self.branch = Branch.objects.get(repository=self.repo, name=self.repo.branch)
        self.branch.head = self.commit3.commitid
        self.branch.save()

        self.client = APIClient()
        self.client.force_login_owner(self.current_owner)

    def _request_file_report(self, path=None, **params):
        url = reverse(
            "api-v2-file-report-detail",
            kwargs={
                "service": "github",
                "owner_username": self.org.username,
                "repo_name": self.repo.name,
                "path": path,
            },
        )

        qs = urlencode(params)
        url = f"{url}?{qs}"
        return self.client.get(url)

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_file_report(self, build_report_from_commit, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.side_effect = [sample_report()]

        res = self._request_file_report(path="foo/file1.py")
        assert res.status_code == 200
        assert res.json() == {
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
            "commit_sha": self.commit3.commitid,
            "commit_file_url": f"{settings.CODECOV_DASHBOARD_URL}/{self.service}/{self.username}/{self.repo_name}/commit/{self.commit3.commitid}/blob/foo/file1.py",
        }

        build_report_from_commit.assert_called_once_with(self.commit3)

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_file_report_no_walk_back(
        self, build_report_from_commit, get_repo_permissions
    ):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.side_effect = [None, sample_report()]

        res = self._request_file_report(path="foo/file1.py")
        assert res.status_code == 404

        build_report_from_commit.assert_called_once_with(self.commit3)

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_file_report_not_enough_walk_back(
        self, build_report_from_commit, get_repo_permissions
    ):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.side_effect = [None, None, sample_report()]

        res = self._request_file_report(path="foo/file1.py", walk_back=1)
        assert res.status_code == 404

        build_report_from_commit.assert_has_calls(
            [call(self.commit3), call(self.commit2)]
        )

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_file_report_with_walk_back(
        self, build_report_from_commit, get_repo_permissions
    ):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.side_effect = [None, None, sample_report()]

        res = self._request_file_report(path="foo/file1.py", walk_back=2)
        assert res.status_code == 200
        assert res.json() == {
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
            "commit_sha": self.commit1.commitid,
            "commit_file_url": f"{settings.CODECOV_DASHBOARD_URL}/{self.service}/{self.username}/{self.repo_name}/commit/{self.commit1.commitid}/blob/foo/file1.py",
        }

        build_report_from_commit.assert_has_calls(
            [call(self.commit3), call(self.commit2), call(self.commit1)]
        )

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_file_report_with_walk_back_oldest_sha(
        self, build_report_from_commit, get_repo_permissions
    ):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.side_effect = [None, None, sample_report()]

        res = self._request_file_report(
            path="foo/file1.py", walk_back=2, oldest_sha=self.commit2.commitid
        )
        assert res.status_code == 404

        # does not walk back to commit1
        build_report_from_commit.assert_has_calls(
            [call(self.commit3), call(self.commit2)]
        )

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_file_report_large_walk_back(
        self, build_report_from_commit, get_repo_permissions
    ):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.side_effect = [sample_report()]

        res = self._request_file_report(path="foo/file1.py", walk_back=21)
        assert res.status_code == 400

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_file_report_walk_back_no_parent(
        self, build_report_from_commit, get_repo_permissions
    ):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.side_effect = [None, None, None]

        res = self._request_file_report(path="foo/file1.py", walk_back=20)
        assert res.status_code == 404

        build_report_from_commit.assert_has_calls(
            [call(self.commit3), call(self.commit2), call(self.commit1)]
        )

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_file_report_walk_back_commit_not_found(
        self, build_report_from_commit, get_repo_permissions
    ):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.side_effect = [None, None, None]

        self.commit3.parent_commit_id = "wrong"
        self.commit3.save()

        res = self._request_file_report(path="foo/file1.py", walk_back=20)
        assert res.status_code == 404

        build_report_from_commit.assert_has_calls([call(self.commit3)])

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_file_report_walk_back_commit_not_complete(
        self, build_report_from_commit, get_repo_permissions
    ):
        get_repo_permissions.return_value = (True, True)

        self.commit1.state = "pending"
        self.commit1.save()

        build_report_from_commit.side_effect = [
            sample_report(),  # skips since the state is pending
            None,  # skips since there's no report
            sample_report(),  # found
        ]

        res = self._request_file_report(path="foo/file1.py", walk_back=20)
        assert res.status_code == 200
        assert res.json() == {
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
            "commit_sha": self.commit3.commitid,
            "commit_file_url": f"{settings.CODECOV_DASHBOARD_URL}/{self.service}/{self.username}/{self.repo_name}/commit/{self.commit3.commitid}/blob/foo/file1.py",
        }

        build_report_from_commit.assert_has_calls([call(self.commit3)])

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_file_report_walk_back_found(
        self, build_report_from_commit, get_repo_permissions
    ):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.side_effect = [None, sample_report(), sample_report()]

        res = self._request_file_report(path="foo/file1.py", walk_back=20)
        assert res.status_code == 200

        build_report_from_commit.assert_has_calls(
            [call(self.commit3), call(self.commit2)]
        )

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_file_report_missing_file(
        self, build_report_from_commit, get_repo_permissions
    ):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.side_effect = [
            sample_report(),
            sample_report(),
            sample_report(),
        ]

        res = self._request_file_report(path="bar/file1.py", walk_back=20)
        assert res.status_code == 404

        build_report_from_commit.assert_has_calls(
            [call(self.commit3), call(self.commit2), call(self.commit1)]
        )

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_file_report_missing_parent_commit(
        self, build_report_from_commit, get_repo_permissions
    ):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.side_effect = [
            sample_report(),
            sample_report(),
            sample_report(),
        ]

        self.commit3.parent_commit_id = None
        self.commit3.save()

        res = self._request_file_report(path="bar/file1.py", walk_back=20)
        assert res.status_code == 404

        build_report_from_commit.assert_has_calls([call(self.commit3)])
