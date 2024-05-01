from unittest.mock import patch
from urllib.parse import urlencode

from django.db import connection
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase
from shared.reports.resources import Report, ReportFile, ReportLine
from shared.utils.sessions import Session

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import BranchFactory, CommitFactory, RepositoryFactory
from services.components import Component
from utils.test_utils import Client


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


class CoverageViewSetTests(APITestCase):
    def _tree(self, **params):
        url = reverse(
            "coverage-tree",
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

        # the order in which these commits are created matters
        # because the branch head is the one that is created
        # later
        self.commit1 = CommitFactory(
            author=self.current_owner,
            repository=self.repo,
        )
        self.commit2 = CommitFactory(
            author=self.current_owner,
            repository=self.repo,
        )
        self.branch = BranchFactory(repository=self.repo, name="test-branch")

        self.commit3 = CommitFactory(
            author=self.current_owner,
            repository=self.repo,
            branch=self.branch,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE branches SET head = %s WHERE branches.repoid = %s AND branches.branch = %s",
                [self.commit3.commitid, self.repo.repoid, self.branch.name],
            )

        self.client = Client()
        self.client.force_login_owner(self.current_owner)

    @patch("shared.reports.api_report_service.build_report_from_commit")
    @patch("services.components.commit_components")
    def test_tree(self, commit_components_mock, build_report_from_commit):
        commit_components_mock.return_value = [
            Component.from_dict(
                {
                    "component_id": "global",
                    "name": "Global",
                    "paths": [".*/*.py"],
                }
            ),
        ]
        build_report_from_commit.return_value = sample_report()
        res = self._tree(components="Global")
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

        build_report_from_commit.assert_called_once_with(self.commit1)

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_tree_sha(self, build_report_from_commit):
        build_report_from_commit.return_value = sample_report()

        res = self._tree(sha=self.commit2.commitid)
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

        build_report_from_commit.assert_called_once_with(self.commit2)

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_tree_missing_sha(self, build_report_from_commit):
        build_report_from_commit.return_value = sample_report()

        res = self._tree(sha="wrong")
        assert res.status_code == 404

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_tree_branch(self, build_report_from_commit):
        build_report_from_commit.return_value = sample_report()

        res = self._tree(branch="test-branch")
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

        build_report_from_commit.assert_called_once_with(self.commit3)

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_tree_missing_branch(self, build_report_from_commit):
        build_report_from_commit.return_value = sample_report()

        res = self._tree(branch="wrong-branch")
        assert res.status_code == 404

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_tree_missing_report(self, build_report_from_commit):
        build_report_from_commit.return_value = None

        res = self._tree()
        assert res.status_code == 404

    @patch("shared.reports.api_report_service.build_report_from_commit")
    @patch("services.components.commit_components")
    def test_tree_no_data_for_components(
        self, commit_components_mock, build_report_from_commit
    ):
        commit_components_mock.return_value = [
            Component.from_dict(
                {
                    "component_id": "c1",
                    "name": "ComponentOne",
                    "paths": ["dne.py"],
                }
            ),
        ]
        build_report_from_commit.return_value = sample_report()
        res = self._tree(components="ComponentOne")
        assert res.json() == []

    @patch("shared.reports.api_report_service.build_report_from_commit")
    @patch("services.components.commit_components")
    def test_tree_not_found_for_components(
        self, commit_components_mock, build_report_from_commit
    ):
        commit_components_mock.return_value = [
            Component.from_dict(
                {
                    "component_id": "c1",
                    "name": "ComponentOne",
                    "paths": ["dne.py"],
                }
            ),
        ]
        build_report_from_commit.return_value = sample_report()
        res = self._tree(components="Does_not_exist")
        assert res.status_code == 404

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_tree_no_data_for_flags(self, build_report_from_commit):
        build_report_from_commit.return_value = sample_report()
        res = self._tree(flags="Does_not_exist")
        assert res.json() == []
