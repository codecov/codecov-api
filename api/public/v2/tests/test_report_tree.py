from unittest.mock import patch
from urllib.parse import urlencode

from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    RepositoryFactory,
)
from shared.reports.resources import Report, ReportFile, ReportLine
from shared.utils.sessions import Session

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
    third_file = ReportFile("file3.py")
    third_file.append(1, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    report.append(first_file)
    report.append(second_file)
    report.append(third_file)
    report.add_session(Session(flags=["flag1", "flag2"]))
    return report


class ReportTreeTests(APITestCase):
    def _tree(self, **params):
        url = reverse(
            "api-v2-report-tree",
            kwargs={
                "service": self.current_owner.service,
                "owner_username": self.current_owner.username,
                "repo_name": self.repo.name,
            },
        )

        qs = urlencode(params)
        url = f"{url}?{qs}"

        return self.client.get(url)

    def setUp(self):
        self.current_owner = OwnerFactory()
        self.repo = RepositoryFactory(author=self.current_owner)
        self.commit = CommitFactory(
            author=self.current_owner,
            repository=self.repo,
        )

        self.client = APIClient()
        self.client.force_login_owner(self.current_owner)

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_tree(self, build_report_from_commit):
        build_report_from_commit.return_value = sample_report()

        res = self._tree()
        assert res.status_code == 200
        assert res.json() == [
            {
                "name": "foo",
                "full_path": "foo",
                "coverage": 62.5,
                "lines": 8,
                "hits": 5,
                "partials": 0,
                "misses": 3,
            },
            {
                "name": "bar",
                "full_path": "bar",
                "coverage": 50.0,
                "lines": 2,
                "hits": 1,
                "partials": 1,
                "misses": 0,
            },
            {
                "name": "file3.py",
                "full_path": "file3.py",
                "coverage": 100.0,
                "lines": 1,
                "hits": 1,
                "partials": 0,
                "misses": 0,
            },
        ]

        build_report_from_commit.assert_called_once_with(self.commit)

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_tree_depth(self, build_report_from_commit):
        build_report_from_commit.return_value = sample_report()

        res = self._tree(depth=2)
        assert res.status_code == 200
        assert res.json() == [
            {
                "name": "foo",
                "full_path": "foo",
                "coverage": 62.5,
                "lines": 8,
                "hits": 5,
                "partials": 0,
                "misses": 3,
                "children": [
                    {
                        "name": "file1.py",
                        "full_path": "foo/file1.py",
                        "coverage": 62.5,
                        "lines": 8,
                        "hits": 5,
                        "partials": 0,
                        "misses": 3,
                    }
                ],
            },
            {
                "name": "bar",
                "full_path": "bar",
                "coverage": 50.0,
                "lines": 2,
                "hits": 1,
                "partials": 1,
                "misses": 0,
                "children": [
                    {
                        "name": "file2.py",
                        "full_path": "bar/file2.py",
                        "coverage": 50.0,
                        "lines": 2,
                        "hits": 1,
                        "partials": 1,
                        "misses": 0,
                    }
                ],
            },
            {
                "name": "file3.py",
                "full_path": "file3.py",
                "coverage": 100.0,
                "lines": 1,
                "hits": 1,
                "partials": 0,
                "misses": 0,
            },
        ]

        build_report_from_commit.assert_called_once_with(self.commit)

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_tree_path(self, build_report_from_commit):
        build_report_from_commit.return_value = sample_report()

        res = self._tree(path="foo")
        assert res.status_code == 200
        assert res.json() == [
            {
                "name": "file1.py",
                "full_path": "foo/file1.py",
                "coverage": 62.5,
                "lines": 8,
                "hits": 5,
                "partials": 0,
                "misses": 3,
            }
        ]

        build_report_from_commit.assert_called_once_with(self.commit)
