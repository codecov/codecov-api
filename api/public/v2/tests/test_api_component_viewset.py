from unittest.mock import patch

from django.test import TestCase
from rest_framework.reverse import reverse
from shared.reports.resources import Report, ReportFile, ReportLine
from shared.utils.sessions import Session

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory
from services.components import Component
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
class ComponentViewSetTestCase(TestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov", service="github")
        self.repo = RepositoryFactory(author=self.org, name="test-repo", active=True)
        self.commit = CommitFactory(repository=self.repo)
        self.current_owner = OwnerFactory(
            username="codecov-user",
            service="github",
            organizations=[self.org.ownerid],
            permission=[self.repo.repoid],
        )

        self.client = APIClient()
        self.client.force_login_owner(self.current_owner)

    def _request_components(self):
        url = reverse(
            "api-v2-components-list",
            kwargs={
                "service": "github",
                "owner_username": self.org.username,
                "repo_name": self.repo.name,
            },
        )
        return self.client.get(url)

    @patch("api.public.v2.component.views.commit_components")
    @patch("shared.reports.api_report_service.build_report_from_commit")
    def test_component_list(
        self, build_report_from_commit, commit_compontents, get_repo_permissions
    ):
        get_repo_permissions.return_value = (True, True)
        build_report_from_commit.side_effect = [sample_report()]
        commit_compontents.return_value = [
            Component(
                component_id="foo",
                paths=[r".*foo"],
                name="Foo",
                flag_regexes=[],
                statuses=[],
            ),
            Component(
                component_id="bar",
                paths=[r".*bar"],
                name="Bar",
                flag_regexes=[],
                statuses=[],
            ),
        ]

        res = self._request_components()
        assert res.status_code == 200
        assert res.json() == [
            {"component_id": "foo", "name": "Foo", "coverage": 62.5},
            {"component_id": "bar", "name": "Bar", "coverage": 50.0},
        ]
