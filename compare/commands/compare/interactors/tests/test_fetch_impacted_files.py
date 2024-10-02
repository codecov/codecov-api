import enum
from unittest.mock import PropertyMock, patch

from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    PullFactory,
    RepositoryFactory,
)
from shared.reports.resources import Report, ReportFile, ReportLine
from shared.utils.sessions import Session

from compare.commands.compare.interactors.fetch_impacted_files import (
    ImpactedFileParameter,
)
from compare.tests.factories import CommitComparisonFactory
from services.comparison import Comparison, ComparisonReport, PullRequestComparison
from services.components import Component

from ..fetch_impacted_files import FetchImpactedFiles


class OrderingDirection(enum.Enum):
    ASC = "ascending"
    DESC = "descending"


mock_data_without_misses = """
{
    "files": [{
        "head_name": "fileA",
        "base_name": "fileA",
        "head_coverage": {
            "hits": 10,
            "misses": 1,
            "partials": 1,
            "branches": 3,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 5
        },
        "base_coverage": {
            "hits": 5,
            "misses": 6,
            "partials": 1,
            "branches": 2,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 4
        },
        "added_diff_coverage": [],
        "unexpected_line_changes": []
    },
    {
        "head_name": "fileB",
        "base_name": "fileB",
        "head_coverage": {
            "hits": 12,
            "misses": 1,
            "partials": 1,
            "branches": 3,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 5
        },
        "base_coverage": {
            "hits": 5,
            "misses": 6,
            "partials": 1,
            "branches": 2,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 4
        },
        "added_diff_coverage": [
            [9,"h"],
            [10,"m"],
            [13,"p"],
            [14,"h"],
            [15,"h"],
            [16,"h"],
            [17,"h"]
        ],
        "unexpected_line_changes": []
    }]
}
"""


mock_data_from_archive = """
{
    "files": [{
        "head_name": "fileA",
        "base_name": "fileA",
        "head_coverage": {
            "hits": 10,
            "misses": 1,
            "partials": 1,
            "branches": 3,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 5
        },
        "base_coverage": {
            "hits": 5,
            "misses": 6,
            "partials": 1,
            "branches": 2,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 4
        },
        "added_diff_coverage": [
            [9,"h"],
            [2,"m"],
            [3,"m"],
            [13,"p"],
            [14,"h"],
            [15,"h"],
            [16,"h"],
            [17,"h"]
        ],
        "unexpected_line_changes": [[[1, "h"], [1, "h"]]]
    },
    {
        "head_name": "fileB",
        "base_name": "fileB",
        "head_coverage": {
            "hits": 12,
            "misses": 1,
            "partials": 1,
            "branches": 3,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 5
        },
        "base_coverage": {
            "hits": 5,
            "misses": 6,
            "partials": 1,
            "branches": 2,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 4
        },
        "added_diff_coverage": [
            [9,"h"],
            [10,"m"],
            [13,"p"],
            [14,"h"],
            [15,"h"],
            [16,"h"],
            [17,"h"]
        ],
        "unexpected_line_changes": [[[1, "h"], [1, "m"]], [[2, "h"], [2, "m"]]]
    }]
}
"""

mocked_files_with_direct_and_indirect_changes = """
{
    "files": [{
        "head_name": "fileA",
        "base_name": "fileA",
        "head_coverage": {
            "hits": 10,
            "misses": 1,
            "partials": 1,
            "branches": 3,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 5
        },
        "base_coverage": {
            "hits": 5,
            "misses": 6,
            "partials": 1,
            "branches": 2,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 4
        },
        "added_diff_coverage": [
            [9,"h"],
            [2,"m"],
            [3,"m"],
            [13,"p"],
            [14,"h"],
            [15,"h"],
            [16,"h"],
            [17,"h"]
        ],
        "unexpected_line_changes": [[[1, "h"], [1, "h"]]]
    },
    {
        "head_name": "fileB",
        "base_name": "fileB",
        "head_coverage": {
            "hits": 12,
            "misses": 1,
            "partials": 1,
            "branches": 3,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 5
        },
        "base_coverage": {
            "hits": 5,
            "misses": 6,
            "partials": 1,
            "branches": 2,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 4
        },
        "added_diff_coverage": [
            [9,"h"],
            [10,"m"],
            [13,"p"],
            [14,"h"],
            [15,"h"],
            [16,"h"],
            [17,"h"]
        ],
        "unexpected_line_changes": []
    },
    {
        "head_name": "fileC",
        "base_name": "fileC",
        "head_coverage": {
            "hits": 12,
            "misses": 1,
            "partials": 1,
            "branches": 3,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 5
        },
        "base_coverage": {
            "hits": 5,
            "misses": 6,
            "partials": 1,
            "branches": 2,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 4
        },
        "added_diff_coverage": [],
        "unexpected_line_changes": [[[1, "h"], [1, "h"]]]
    }]
}
"""


mocked_component_files_with_direct_and_indirect_changes = """
{
    "files": [{
        "head_name": "fileA.py",
        "base_name": "fileA.py",
        "head_coverage": {
            "hits": 10,
            "misses": 1,
            "partials": 1,
            "branches": 3,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 5
        },
        "base_coverage": {
            "hits": 5,
            "misses": 6,
            "partials": 1,
            "branches": 2,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 4
        },
        "added_diff_coverage": [
            [9,"h"],
            [2,"m"],
            [3,"m"],
            [13,"p"],
            [14,"h"],
            [15,"h"],
            [16,"h"],
            [17,"h"]
        ],
        "unexpected_line_changes": [[[1, "h"], [1, "h"]]]
    },
    {
        "head_name": "fileB.js",
        "base_name": "fileB.js",
        "head_coverage": {
            "hits": 12,
            "misses": 1,
            "partials": 1,
            "branches": 3,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 5
        },
        "base_coverage": {
            "hits": 5,
            "misses": 6,
            "partials": 1,
            "branches": 2,
            "sessions": 0,
            "complexity": 0,
            "complexity_total": 0,
            "methods": 4
        },
        "added_diff_coverage": [
            [9,"h"],
            [10,"m"],
            [13,"p"],
            [14,"h"],
            [15,"h"],
            [16,"h"],
            [17,"h"]
        ],
        "unexpected_line_changes": []
    }]
}
"""


class FetchImpactedFilesTest(TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")
        self.parent_commit = CommitFactory()
        self.commit = CommitFactory(
            parent_commit_id=self.parent_commit.commitid,
            repository=self.parent_commit.repository,
        )
        self.commit_comparison = CommitComparisonFactory(
            base_commit=self.parent_commit,
            compare_commit=self.commit,
            report_storage_path="v4/test.json",
        )
        self.comparison_report = ComparisonReport(self.commit_comparison)

    # helper to execute the interactor
    def execute(self, owner, *args):
        service = owner.service if owner else "github"
        return FetchImpactedFiles(owner, service).execute(*args)

    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_impacted_file_sort_function(self, read_file):
        read_file.return_value = mock_data_from_archive
        parameter = ImpactedFileParameter.CHANGE_COVERAGE
        direction = OrderingDirection.ASC
        filters = {"ordering": {"parameter": parameter, "direction": direction}}
        comparison = None
        sorted_files = self.execute(None, self.comparison_report, comparison, filters)
        assert [file.head_name for file in sorted_files] == ["fileA", "fileB"]

    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_impacted_file_sort_function_no_misses(self, read_file):
        read_file.return_value = mock_data_without_misses
        parameter = ImpactedFileParameter.MISSES_COUNT
        direction = OrderingDirection.ASC
        filters = {"ordering": {"parameter": parameter, "direction": direction}}
        comparison = None
        sorted_files = self.execute(None, self.comparison_report, comparison, filters)
        assert [file.head_name for file in sorted_files] == ["fileA", "fileB"]

    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_impacted_file_sort_function_error(self, read_file):
        read_file.return_value = mock_data_from_archive
        parameter = "something else"
        direction = OrderingDirection.DESC
        filters = {"ordering": {"parameter": parameter, "direction": direction}}
        comparison = None

        with self.assertRaises(ValueError) as ctx:
            self.execute(None, self.comparison_report, comparison, filters)
        self.assertEqual(
            "invalid impacted file parameter: something else", str(ctx.exception)
        )

    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_change_coverage_ascending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.CHANGE_COVERAGE,
            }
        }
        comparison = None
        impacted_files = self.execute(None, self.comparison_report, comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileA", "fileB"]

    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_change_coverage_descending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.DESC,
                "parameter": ImpactedFileParameter.CHANGE_COVERAGE,
            }
        }
        comparison = None
        impacted_files = self.execute(None, self.comparison_report, comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileB", "fileA"]

    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_head_coverage_ascending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.HEAD_COVERAGE,
            }
        }
        comparison = None
        impacted_files = self.execute(None, self.comparison_report, comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileA", "fileB"]

    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_patch_coverage_ascending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.PATCH_COVERAGE,
            }
        }
        comparison = None
        impacted_files = self.execute(None, self.comparison_report, comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileA", "fileB"]

    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_patch_coverage_descending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.DESC,
                "parameter": ImpactedFileParameter.PATCH_COVERAGE,
            }
        }
        comparison = None
        impacted_files = self.execute(None, self.comparison_report, comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileB", "fileA"]

    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_head_coverage_descending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.DESC,
                "parameter": ImpactedFileParameter.HEAD_COVERAGE,
            }
        }
        comparison = None
        impacted_files = self.execute(None, self.comparison_report, comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileB", "fileA"]

    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_head_name_ascending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.FILE_NAME,
            }
        }
        comparison = None
        impacted_files = self.execute(None, self.comparison_report, comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileA", "fileB"]

    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_head_name_descending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.DESC,
                "parameter": ImpactedFileParameter.FILE_NAME,
            }
        }
        comparison = None
        impacted_files = self.execute(None, self.comparison_report, comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileB", "fileA"]

    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_misses_count_ascending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.MISSES_COUNT,
            }
        }
        comparison = None
        impacted_files = self.execute(None, self.comparison_report, comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileA", "fileB"]

    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_misses_count_descending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.DESC,
                "parameter": ImpactedFileParameter.MISSES_COUNT,
            }
        }
        comparison = None
        impacted_files = self.execute(None, self.comparison_report, comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileB", "fileA"]

    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_impacted_files_without_filters(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {}
        comparison = None
        impacted_files = self.execute(None, self.comparison_report, comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileA", "fileB"]

    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_unintended_changes(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "has_unintended_changes": True,
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.FILE_NAME,
            },
        }
        comparison = None
        impacted_files = self.execute(None, self.comparison_report, comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileA", "fileB"]

    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_unintended_changes_set_to_false(
        self, read_file
    ):
        read_file.return_value = mocked_files_with_direct_and_indirect_changes
        filters = {
            "has_unintended_changes": False,
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.FILE_NAME,
            },
        }
        comparison = None
        impacted_files = self.execute(None, self.comparison_report, comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileA", "fileB"]

    @patch("services.comparison.Comparison.head_report", new_callable=PropertyMock)
    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_flags_and_commit_comparison_for_pull(
        self, read_file, build_report_from_commit_mock
    ):
        read_file.return_value = mocked_files_with_direct_and_indirect_changes

        commit_report = Report()
        session_a_id, _ = commit_report.add_session(Session(flags=["flag-123"]))
        session_b_id, _ = commit_report.add_session(Session(flags=["flag-456"]))
        file_a = ReportFile("fileA")
        file_a.append(1, ReportLine.create(coverage=1, sessions=[[session_a_id, 1]]))
        commit_report.append(file_a)
        file_b = ReportFile("fileB")
        file_b.append(1, ReportLine.create(coverage=1, sessions=[[session_b_id, 1]]))
        commit_report.append(file_b)
        build_report_from_commit_mock.return_value = commit_report

        flags = ["flag-123"]
        filters = {"flags": flags}

        owner = OwnerFactory()
        repo = RepositoryFactory(author=owner)
        base, head, compared_to = (
            CommitFactory(repository=repo),
            CommitFactory(repository=repo),
            CommitFactory(repository=repo),
        )
        pull = PullFactory(
            pullid=256,
            repository=repo,
            base=base.commitid,
            head=head.commitid,
            compared_to=compared_to.commitid,
        )
        comparison = PullRequestComparison(user=owner, pull=pull)

        impacted_files = self.execute(None, self.comparison_report, comparison, filters)
        assert len(impacted_files) == 1
        assert impacted_files[0].head_name == "fileA"

    @patch("services.comparison.Comparison.head_report", new_callable=PropertyMock)
    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_flags_and_commit_comparison_for_parent_commit(
        self, read_file, build_report_from_commit_mock
    ):
        read_file.return_value = mocked_files_with_direct_and_indirect_changes

        commit_report = Report()
        session_a_id, _ = commit_report.add_session(Session(flags=["flag-123"]))
        session_b_id, _ = commit_report.add_session(Session(flags=["flag-456"]))
        file_a = ReportFile("fileA")
        file_a.append(1, ReportLine.create(coverage=1, sessions=[[session_a_id, 1]]))
        commit_report.append(file_a)
        file_b = ReportFile("fileB")
        file_b.append(1, ReportLine.create(coverage=1, sessions=[[session_b_id, 1]]))
        commit_report.append(file_b)
        build_report_from_commit_mock.return_value = commit_report

        flags = ["flag-123"]
        filters = {"flags": flags}

        owner = OwnerFactory()
        repo = RepositoryFactory(author=owner)
        base, head = (
            CommitFactory(repository=repo),
            CommitFactory(repository=repo),
        )
        comparison = Comparison(user=owner, base_commit=base, head_commit=head)

        impacted_files = self.execute(None, self.comparison_report, comparison, filters)
        assert len(impacted_files) == 1
        assert impacted_files[0].head_name == "fileA"

    @patch("services.components.commit_components")
    @patch("services.comparison.Comparison.head_report", new_callable=PropertyMock)
    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_components_and_commit_comparison_for_parent_commit(
        self, read_file, build_report_from_commit_mock, commit_components_mock
    ):
        read_file.return_value = mocked_component_files_with_direct_and_indirect_changes

        commit_report = Report()
        session_a_id, _ = commit_report.add_session(Session(flags=["flag-123"]))
        session_b_id, _ = commit_report.add_session(Session(flags=["flag-456"]))
        file_a = ReportFile("fileA.py")
        file_a.append(1, ReportLine.create(coverage=1, sessions=[[session_a_id, 1]]))
        commit_report.append(file_a)
        file_b = ReportFile("fileB.js")
        file_b.append(1, ReportLine.create(coverage=1, sessions=[[session_b_id, 1]]))
        commit_report.append(file_b)
        build_report_from_commit_mock.return_value = commit_report

        filters = {"components": ["PYThon"]}

        owner = OwnerFactory()
        repo = RepositoryFactory(author=owner)
        base, head = (
            CommitFactory(repository=repo),
            CommitFactory(repository=repo),
        )

        # components filter
        commit_components_mock.return_value = [
            Component.from_dict(
                {"component_id": "python1.1", "paths": [".*/*.py"], "name": "PYThon"}
            ),
            Component.from_dict(
                {"component_id": "golang1.2", "paths": [".*/*.go"], "name": "GOLang"}
            ),
        ]
        comparison = Comparison(user=owner, base_commit=base, head_commit=head)

        impacted_files = self.execute(None, self.comparison_report, comparison, filters)
        assert len(impacted_files) == 1
        assert impacted_files[0].head_name == "fileA.py"

    @patch("services.components.commit_components")
    @patch("services.comparison.Comparison.head_report", new_callable=PropertyMock)
    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_components_using_flags(
        self, read_file, build_report_from_commit_mock, commit_components_mock
    ):
        read_file.return_value = mocked_component_files_with_direct_and_indirect_changes

        commit_report = Report()
        session_a_id, _ = commit_report.add_session(Session(flags=["flag-123"]))
        session_b_id, _ = commit_report.add_session(Session(flags=["flag-456"]))
        file_a = ReportFile("fileA.py")
        file_a.append(1, ReportLine.create(coverage=1, sessions=[[session_a_id, 1]]))
        commit_report.append(file_a)
        file_b = ReportFile("fileB.js")
        file_b.append(1, ReportLine.create(coverage=1, sessions=[[session_b_id, 1]]))
        commit_report.append(file_b)
        build_report_from_commit_mock.return_value = commit_report

        filters = {"components": ["javascript"]}

        owner = OwnerFactory()
        repo = RepositoryFactory(author=owner)
        base, head = (
            CommitFactory(repository=repo),
            CommitFactory(repository=repo),
        )

        # components filter
        commit_components_mock.return_value = [
            Component.from_dict(
                {"component_id": "python1.1", "paths": [".*/*.py"], "name": "PYThon"}
            ),
            Component.from_dict(
                {
                    "component_id": "javascript1.2",
                    "name": "javascript",
                    "flags_regexes": "flag-123",
                }
            ),
        ]
        comparison = Comparison(user=owner, base_commit=base, head_commit=head)

        impacted_files = self.execute(None, self.comparison_report, comparison, filters)

        assert len(impacted_files) == 2
        assert impacted_files[0].head_name == "fileA.py"
        assert impacted_files[1].head_name == "fileB.js"

    @patch("services.components.commit_components")
    @patch("services.comparison.Comparison.head_report", new_callable=PropertyMock)
    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_components_and_flags_commit_comparison_for_parent_commit(
        self, read_file, build_report_from_commit_mock, commit_components_mock
    ):
        read_file.return_value = mocked_component_files_with_direct_and_indirect_changes

        commit_report = Report()
        session_a_id, _ = commit_report.add_session(Session(flags=["flag-123"]))
        session_b_id, _ = commit_report.add_session(Session(flags=["flag-456"]))
        file_a = ReportFile("fileA.py")
        file_a.append(1, ReportLine.create(coverage=1, sessions=[[session_a_id, 1]]))
        commit_report.append(file_a)
        file_b = ReportFile("fileB.js")
        file_b.append(1, ReportLine.create(coverage=1, sessions=[[session_b_id, 1]]))
        commit_report.append(file_b)
        build_report_from_commit_mock.return_value = commit_report

        filters = {"components": ["PYThon"], "flags": ["flag-123"]}

        owner = OwnerFactory()
        repo = RepositoryFactory(author=owner)
        base, head = (
            CommitFactory(repository=repo),
            CommitFactory(repository=repo),
        )

        # components filter
        commit_components_mock.return_value = [
            Component.from_dict(
                {
                    "component_id": "python1.1",
                    "paths": [".*/*.py"],
                    "name": "PYThon",
                    "flag_regexes": "flag-123",
                }
            ),
            Component.from_dict(
                {
                    "component_id": "javascript.2",
                    "paths": [".*/*.js"],
                    "name": "javaScript",
                    "flag_regexes": "flag-456",
                }
            ),
        ]
        comparison = Comparison(user=owner, base_commit=base, head_commit=head)

        impacted_files = self.execute(None, self.comparison_report, comparison, filters)
        assert len(impacted_files) == 1
        assert impacted_files[0].head_name == "fileA.py"
