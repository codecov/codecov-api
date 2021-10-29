import json
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase
from shared.reports.types import ReportTotals

from compare.tests.factories import CommitComparisonFactory
from core.tests.factories import CommitFactory

from ..get_impacted_files import GetImpactedFilesInteractor


class GetImpactedFilesInteractorTest(TransactionTestCase):
    def setUp(self):
        self.user = AnonymousUser()
        self.parent_commit = CommitFactory()
        self.commit = CommitFactory(
            parent_commit_id=self.parent_commit.commitid,
            repository=self.parent_commit.repository,
        )
        self.comparison = CommitComparisonFactory()
        self.comparison_with_storage = CommitComparisonFactory(
            report_storage_path="v4/test.json"
        )

    async def test_when_comparison_do_not_have_storage_path(self):
        files = await GetImpactedFilesInteractor(AnonymousUser(), "github").execute(
            self.comparison
        )
        assert files == []

    @patch("services.archive.ArchiveService.read_file")
    @async_to_sync
    async def test_when_failing_getting_file_from_storge(self, mock_read_file):
        mock_read_file.side_effect = Exception()
        files = await GetImpactedFilesInteractor(AnonymousUser(), "github").execute(
            self.comparison_with_storage
        )
        assert files == []

    @patch("services.archive.ArchiveService.read_file")
    @async_to_sync
    async def test_when_fetching_file(self, mock_read_file):
        mock_read_file.return_value = json.dumps(
            {
                "files": [
                    {
                        "base_name": "src/App.js",
                        "head_name": "src/App.js",
                        "file_was_added_by_diff": False,
                        "file_was_removed_by_diff": False,
                        "base_coverage": None,
                        "head_coverage": None,
                        "removed_diff_coverage": [],
                        "added_diff_coverage": None,
                        "unexpected_line_changes": [],
                    },
                    {
                        "base_name": "src/config.js",
                        "head_name": "src/config.js",
                        "file_was_added_by_diff": False,
                        "file_was_removed_by_diff": False,
                        "base_coverage": {
                            "hits": 4,
                            "misses": 0,
                            "partials": 0,
                            "branches": 0,
                            "sessions": 0,
                            "complexity": 0,
                            "complexity_total": 0,
                            "methods": 2,
                        },
                        "head_coverage": {
                            "hits": 4,
                            "misses": 2,
                            "partials": 0,
                            "branches": 0,
                            "sessions": 0,
                            "complexity": 0,
                            "complexity_total": 0,
                            "methods": 3,
                        },
                        "removed_diff_coverage": [],
                        "added_diff_coverage": [[25, "m"], [26, "m"]],
                        "unexpected_line_changes": [],
                    },
                    {
                        "base_name": "src/utils.js",
                        "head_name": "src/utils.js",
                        "file_was_added_by_diff": False,
                        "file_was_removed_by_diff": False,
                        "base_coverage": None,
                        "head_coverage": {
                            "hits": 0,
                            "misses": 0,
                            "partials": 0,
                            "branches": 0,
                            "sessions": 0,
                            "complexity": 0,
                            "complexity_total": 0,
                            "methods": 0,
                        },
                        "removed_diff_coverage": [],
                        "added_diff_coverage": [[0, "h"], [1, "m"], [1, "p"]],
                        "unexpected_line_changes": [],
                    },
                ]
            }
        )
        files = await GetImpactedFilesInteractor(AnonymousUser(), "github").execute(
            self.comparison_with_storage
        )
        mock_read_file.assert_called_once_with(
            self.comparison_with_storage.report_storage_path
        )
        assert files == [
            {
                "head_name": "src/App.js",
                "base_name": "src/App.js",
                "file_was_added_by_diff": False,
                "file_was_removed_by_diff": False,
                "removed_diff_coverage": [],
                "added_diff_coverage": None,
                "unexpected_line_changes": [],
                "base_coverage": None,
                "head_coverage": None,
                "patch_coverage": None,
            },
            {
                "head_name": "src/config.js",
                "base_name": "src/config.js",
                "file_was_added_by_diff": False,
                "file_was_removed_by_diff": False,
                "removed_diff_coverage": [],
                "added_diff_coverage": [[25, "m"], [26, "m"]],
                "unexpected_line_changes": [],
                "base_coverage": ReportTotals(
                    files=0,
                    lines=0,
                    hits=4,
                    misses=0,
                    partials=0,
                    coverage=100.0,
                    branches=0,
                    methods=2,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                "head_coverage": ReportTotals(
                    files=0,
                    lines=0,
                    hits=4,
                    misses=2,
                    partials=0,
                    coverage=(200 / 3),
                    branches=0,
                    methods=3,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                "patch_coverage": ReportTotals(
                    files=0,
                    lines=0,
                    hits=0,
                    misses=2,
                    partials=0,
                    coverage=0.0,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
            },
            {
                "head_name": "src/utils.js",
                "base_name": "src/utils.js",
                "file_was_added_by_diff": False,
                "file_was_removed_by_diff": False,
                "removed_diff_coverage": [],
                "added_diff_coverage": [[0, "h"], [1, "m"], [1, "p"]],
                "unexpected_line_changes": [],
                "base_coverage": None,
                "head_coverage": ReportTotals(
                    files=0,
                    lines=0,
                    hits=0,
                    misses=0,
                    partials=0,
                    coverage=None,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
                "patch_coverage": ReportTotals(
                    files=0,
                    lines=0,
                    hits=1,
                    misses=1,
                    partials=1,
                    coverage=100 / 3,
                    branches=0,
                    methods=0,
                    messages=0,
                    sessions=0,
                    complexity=0,
                    complexity_total=0,
                    diff=0,
                ),
            },
        ]
