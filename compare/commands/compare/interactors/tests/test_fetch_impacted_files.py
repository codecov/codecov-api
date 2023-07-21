import enum
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from compare.commands.compare.interactors.fetch_impacted_files import (
    ImpactedFileParameter,
)
from compare.tests.factories import CommitComparisonFactory
from core.tests.factories import CommitFactory
from services.comparison import ComparisonReport

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
        self.comparison = ComparisonReport(self.commit_comparison)

    # helper to execute the interactor
    def execute(self, owner, *args):
        service = owner.service if owner else "github"
        return FetchImpactedFiles(owner, service).execute(*args)

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_file_sort_function(self, read_file):
        read_file.return_value = mock_data_from_archive
        parameter = ImpactedFileParameter.CHANGE_COVERAGE
        direction = OrderingDirection.ASC
        filters = {"ordering": {"parameter": parameter, "direction": direction}}
        sorted_files = self.execute(None, self.comparison, filters)
        assert [file.head_name for file in sorted_files] == ["fileA", "fileB"]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_file_sort_function_no_misses(self, read_file):
        read_file.return_value = mock_data_without_misses
        parameter = ImpactedFileParameter.MISSES_COUNT
        direction = OrderingDirection.ASC
        filters = {"ordering": {"parameter": parameter, "direction": direction}}
        sorted_files = self.execute(None, self.comparison, filters)
        assert [file.head_name for file in sorted_files] == ["fileA", "fileB"]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_file_sort_function_error(self, read_file):
        read_file.return_value = mock_data_from_archive
        parameter = "something else"
        direction = OrderingDirection.DESC
        filters = {"ordering": {"parameter": parameter, "direction": direction}}

        with self.assertRaises(ValueError) as ctx:
            self.execute(None, self.comparison, filters)
        self.assertEqual(
            "invalid impacted file parameter: something else", str(ctx.exception)
        )

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_change_coverage_ascending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.CHANGE_COVERAGE,
            }
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileA", "fileB"]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_change_coverage_descending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.DESC,
                "parameter": ImpactedFileParameter.CHANGE_COVERAGE,
            }
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileB", "fileA"]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_head_coverage_ascending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.HEAD_COVERAGE,
            }
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileA", "fileB"]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_patch_coverage_ascending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.PATCH_COVERAGE,
            }
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileA", "fileB"]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_patch_coverage_descending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.DESC,
                "parameter": ImpactedFileParameter.PATCH_COVERAGE,
            }
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileB", "fileA"]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_head_coverage_descending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.DESC,
                "parameter": ImpactedFileParameter.HEAD_COVERAGE,
            }
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileB", "fileA"]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_head_name_ascending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.FILE_NAME,
            }
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileA", "fileB"]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_head_name_descending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.DESC,
                "parameter": ImpactedFileParameter.FILE_NAME,
            }
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileB", "fileA"]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_misses_count_ascending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.MISSES_COUNT,
            }
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileA", "fileB"]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_misses_count_descending(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "ordering": {
                "direction": OrderingDirection.DESC,
                "parameter": ImpactedFileParameter.MISSES_COUNT,
            }
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileB", "fileA"]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_without_filters(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {}
        impacted_files = self.execute(None, self.comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileA", "fileB"]

    @patch("services.archive.ArchiveService.read_file")
    def test_impacted_files_filtered_by_unintended_changes(self, read_file):
        read_file.return_value = mock_data_from_archive
        filters = {
            "has_unintended_changes": True,
            "ordering": {
                "direction": OrderingDirection.ASC,
                "parameter": ImpactedFileParameter.FILE_NAME,
            },
        }
        impacted_files = self.execute(None, self.comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileA", "fileB"]

    @patch("services.archive.ArchiveService.read_file")
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
        impacted_files = self.execute(None, self.comparison, filters)
        assert [file.head_name for file in impacted_files] == ["fileA", "fileB"]
