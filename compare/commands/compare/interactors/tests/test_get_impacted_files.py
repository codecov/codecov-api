import json
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase
from shared.reports.types import ReportTotals

from core.tests.factories import CommitFactory
from compare.tests.factories import CommitComparisonFactory
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
            [
                {
                    "path": "src/config.js",
                    "base_totals": [0, 4, 4, 0, 0, "100", 0, 2, 0, 0, 0, 0, 0],
                    "compare_totals": [0, 6, 4, 2, 0, "66.66667", 0, 3, 0, 0, 0, 0, 0],
                    "patch": [0, 2, 0, 2, 0, "0", 0, 1, 0, 0, 0, 0, 0],
                    "new": False,
                    "deleted": False,
                    "in_diff": True,
                    "old_path": None,
                },
                {
                    "path": "src/App.js",
                    "base_totals": None,
                    "compare_totals": None,
                    "patch": None,
                    "new": False,
                    "deleted": False,
                    "in_diff": True,
                    "old_path": None,
                },
            ]
        )
        files = await GetImpactedFilesInteractor(AnonymousUser(), "github").execute(
            self.comparison_with_storage
        )
        mock_read_file.assert_called_once_with(
            self.comparison_with_storage.report_storage_path
        )
        assert files == [
            {
                "path": "src/config.js",
                "base_totals": ReportTotals(0, 4, 4, 0, 0, "100", 0, 2, 0, 0, 0, 0, 0),
                "compare_totals": ReportTotals(
                    0, 6, 4, 2, 0, "66.66667", 0, 3, 0, 0, 0, 0, 0
                ),
                "patch": ReportTotals(0, 2, 0, 2, 0, "0", 0, 1, 0, 0, 0, 0, 0),
                "new": False,
                "deleted": False,
                "in_diff": True,
                "old_path": None,
            },
            {
                "path": "src/App.js",
                "base_totals": None,
                "compare_totals": None,
                "patch": None,
                "new": False,
                "deleted": False,
                "in_diff": True,
                "old_path": None,
            },
        ]
