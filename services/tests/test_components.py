from unittest.mock import PropertyMock, patch

from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase
from shared.components import Component
from shared.reports.resources import Report, ReportFile, ReportLine
from shared.utils.sessions import Session
from shared.yaml.user_yaml import UserYaml

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import CommitFactory, RepositoryFactory
from services.comparison import Comparison
from services.components import (
    ComponentComparison,
    commit_components,
    component_filtered_report,
)


def sample_report():
    report = Report()
    first_file = ReportFile("file_1.go")
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
    second_file = ReportFile("file_2.py")
    second_file.append(12, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    second_file.append(
        51, ReportLine.create(coverage="1/2", type="b", sessions=[[0, 1]])
    )
    report.append(first_file)
    report.append(second_file)
    report.add_session(Session(flags=["flag1", "flag2"]))
    return report


class ComponentServiceTest(TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory()
        self.repo = RepositoryFactory(author=self.org, private=False)
        self.commit = CommitFactory(repository=self.repo)

    @patch("services.components.final_commit_yaml")
    def test_commit_components(self, mock_final_yaml):
        mock_final_yaml.return_value = UserYaml(
            {
                "component_management": {
                    "default_rules": {
                        "paths": [r".*\.py"],
                        "flag_regexes": [r"flag.*"],
                    },
                    "individual_components": [
                        {"component_id": "go_files", "paths": [r".*\.go"]},
                        {"component_id": "rules_from_default"},
                        {
                            "component_id": "I have my flags",
                            "flag_regexes": [r"python-.*"],
                        },
                        {
                            "component_id": "required",
                            "name": "display",
                            "flag_regexes": [],
                            "paths": [r"src/.*"],
                        },
                    ],
                }
            }
        )

        user = AnonymousUser()
        components = commit_components(self.commit, user)
        assert components == [
            Component(
                component_id="go_files",
                paths=[r".*\.go"],
                name="",
                flag_regexes=[r"flag.*"],
                statuses=[],
            ),
            Component(
                component_id="rules_from_default",
                paths=[r".*\.py"],
                name="",
                flag_regexes=[r"flag.*"],
                statuses=[],
            ),
            Component(
                component_id="I have my flags",
                paths=[r".*\.py"],
                name="",
                flag_regexes=[r"python-.*"],
                statuses=[],
            ),
            Component(
                component_id="required",
                name="display",
                paths=[r"src/.*"],
                flag_regexes=[],
                statuses=[],
            ),
        ]

        mock_final_yaml.assert_called_once_with(self.commit, user)

    def test_component_filtered_report(self):
        report = sample_report()

        component_go = Component.from_dict(
            {
                "component_id": "golang",
                "paths": [".*/*.go"],
            }
        )
        report_go = component_filtered_report(report, component_go)
        assert report_go.files == ["file_1.go"]
        assert report_go.totals.coverage == report.get("file_1.go").totals.coverage

        component_py = Component.from_dict(
            {
                "component_id": "python",
                "paths": [".*/*.py"],
            }
        )
        report_py = component_filtered_report(report, component_py)
        assert report_py.files == ["file_2.py"]
        assert report_py.totals.coverage == report.get("file_2.py").totals.coverage


class ComponentComparisonTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory()
        self.repo = RepositoryFactory(author=self.user)
        self.base_commit = CommitFactory(repository=self.repo)
        self.head_commit = CommitFactory(repository=self.repo)
        self.comparison = Comparison(self.user, self.base_commit, self.head_commit)

    @patch("services.comparison.Comparison.base_report", new_callable=PropertyMock)
    def test_head_report(self, base_report_mock):
        report = sample_report()
        base_report_mock.return_value = report

        component_go = Component.from_dict(
            {
                "component_id": "golang",
                "paths": [".*/*.go"],
            }
        )
        component_comparison = ComponentComparison(self.comparison, component_go)
        assert component_comparison.head_report.files == ["file_1.go"]
        assert (
            component_comparison.head_report.totals.coverage
            == report.get("file_1.go").totals.coverage
        )

    @patch("services.comparison.Comparison.head_report", new_callable=PropertyMock)
    def test_head_report(self, head_report_mock):
        report = sample_report()
        head_report_mock.return_value = report

        component_go = Component.from_dict(
            {
                "component_id": "golang",
                "paths": [".*/*.go"],
            }
        )
        component_comparison = ComponentComparison(self.comparison, component_go)
        assert component_comparison.head_report.files == ["file_1.go"]
        assert (
            component_comparison.head_report.totals.coverage
            == report.get("file_1.go").totals.coverage
        )

    @patch("services.comparison.Comparison.git_comparison", new_callable=PropertyMock)
    @patch("services.comparison.Comparison.head_report", new_callable=PropertyMock)
    def test_patch_totals(self, head_report_mock, git_comparison_mock):
        report = sample_report()
        head_report_mock.return_value = report

        git_comparison_mock.return_value = {
            "diff": {
                "files": {
                    "file_1.go": {
                        "type": "modified",
                        "segments": [
                            {
                                "header": ["1", "2", "1", "1"],
                                "lines": ["-line", "+line", "+another line"],
                            }
                        ],
                    },
                    "file_2.py": {
                        "type": "modified",
                        "segments": [
                            {
                                "header": ["1", "1", "1", "1"],
                                "lines": ["-line", "+line"],
                            }
                        ],
                    },
                }
            }
        }

        component_go = Component.from_dict(
            {
                "component_id": "golang",
                "paths": [".*/*.go"],
            }
        )
        component_comparison = ComponentComparison(self.comparison, component_go)

        # removed 1 tested line, added 1 tested and 1 untested line
        assert component_comparison.patch_totals.coverage == "50.00000"
