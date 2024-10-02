from unittest.mock import patch

from django.test import TestCase
from rest_framework.reverse import reverse
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    RepositoryFactory,
)
from shared.reports.resources import Report, ReportFile, ReportLine
from shared.utils.sessions import Session

from reports.tests.factories import RepositoryFlagFactory
from utils.test_utils import APIClient


def flags_report():
    report = Report()
    session_a_id, _ = report.add_session(Session(flags=["foo"]))
    session_b_id, _ = report.add_session(Session(flags=["bar"]))

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
class FlagViewSetTestCase(TestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov", service="github")
        self.repo = RepositoryFactory(author=self.org, name="test-repo", active=True)
        self.current_owner = OwnerFactory(
            username="codecov-user",
            service="github",
            organizations=[self.org.ownerid],
            permission=[self.repo.repoid],
        )
        self.flag1 = RepositoryFlagFactory(flag_name="foo", repository=self.repo)
        self.flag2 = RepositoryFlagFactory(flag_name="bar", repository=self.repo)
        self.flag2 = RepositoryFlagFactory(flag_name="baz")

        self.client = APIClient()
        self.client.force_login_owner(self.current_owner)

    def _request_flags(self):
        url = reverse(
            "api-v2-flags-list",
            kwargs={
                "service": "github",
                "owner_username": self.org.username,
                "repo_name": self.repo.name,
            },
        )
        return self.client.get(url)

    def test_flag_list_no_commit(self, get_repo_permissions):
        get_repo_permissions.return_value = (True, True)

        res = self._request_flags()
        assert res.status_code == 200
        assert res.json() == {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {"flag_name": "foo", "coverage": None},
                {"flag_name": "bar", "coverage": None},
            ],
            "total_pages": 1,
        }

    def test_flag_list_no_report(self, get_repo_permissions):
        CommitFactory(
            author=self.org,
            repository=self.repo,
            branch=self.repo.branch,
        )
        get_repo_permissions.return_value = (True, True)

        res = self._request_flags()
        assert res.status_code == 200
        assert res.json() == {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {"flag_name": "foo", "coverage": None},
                {"flag_name": "bar", "coverage": None},
            ],
            "total_pages": 1,
        }

    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_flag_list_with_coverage(
        self, build_report_from_commit, get_repo_permissions
    ):
        CommitFactory(
            author=self.org,
            repository=self.repo,
            branch=self.repo.branch,
        )
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.return_value = flags_report()

        res = self._request_flags()
        assert res.status_code == 200
        assert res.json() == {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {"flag_name": "foo", "coverage": 62.5},
                {"flag_name": "bar", "coverage": 100},
            ],
            "total_pages": 1,
        }
