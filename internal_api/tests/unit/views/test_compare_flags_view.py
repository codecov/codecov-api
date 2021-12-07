from pathlib import Path
from unittest.mock import PropertyMock, patch

from rest_framework.reverse import reverse
from shared.reports.types import ReportTotals

from codecov.tests.base_test import InternalAPITest
from core.tests.factories import CommitFactory, PullFactory, RepositoryFactory

current_file = Path(__file__)


@patch("services.comparison.Comparison.git_comparison", new_callable=PropertyMock)
@patch("services.archive.ArchiveService.read_chunks")
@patch("shared.reports.filtered.FilteredReport.apply_diff")
@patch(
    "internal_api.repo.repository_accessors.RepoAccessors.get_repo_permissions",
    lambda self, repo, user: (True, True),
)
class TestCompareFlagsView(InternalAPITest):
    def _get_compare_flags(self, kwargs, query_params):
        return self.client.get(
            reverse("compare-flags", kwargs=kwargs), data=query_params
        )

    def setUp(self):
        self.repo = RepositoryFactory.create(author__username="ThiagoCodecov")
        self.parent_commit = CommitFactory.create(
            commitid="00c7b4b49778b3c79427f9c4c13a8612a376ff19", repository=self.repo
        )
        self.commit = CommitFactory.create(
            message="test_report_serializer",
            commitid="68946ef98daec68c7798459150982fc799c87d85",
            parent_commit_id=self.parent_commit.commitid,
            repository=self.repo,
        )

        self.client.force_login(self.repo.author)

    def test_compare_flags___success(
        self, diff_totals_mock, read_chunks_mock, git_comparison_mock,
    ):
        head_chunks = open(
            current_file.parent.parent.parent
            / f"samples/{self.commit.commitid}_chunks.txt",
            "r",
        ).read()
        base_chunks = open(
            current_file.parent.parent.parent
            / f"samples/{self.parent_commit.commitid}_chunks.txt",
            "r",
        ).read()
        read_chunks_mock.side_effect = (
            lambda x: head_chunks if x == self.commit.commitid else base_chunks
        )
        diff_totals_mock.return_value = ReportTotals(
            files=0,
            lines=0,
            hits=0,
            misses=0,
            partials=0,
            coverage="0",
            branches=0,
            methods=0,
            messages=0,
            sessions=0,
            complexity=0,
            complexity_total=0,
            diff=0,
        )
        git_comparison_mock.return_value = {"diff": {"files": {}}}
        response = self._get_compare_flags(
            kwargs={
                "service": self.repo.author.service,
                "owner_username": self.repo.author.username,
                "repo_name": self.repo.name,
            },
            query_params={
                "base": self.parent_commit.commitid,
                "head": self.commit.commitid,
            },
        )

        assert response.status_code == 200

        expected_result = [
            {
                "name": "unittests",
                "base_report_totals": {
                    "branches": 0,
                    "complexity": 0,
                    "complexity_total": 0,
                    "complexity_ratio": 0,
                    "coverage": 79.17,
                    "diff": 0,
                    "files": 3,
                    "hits": 19,
                    "lines": 24,
                    "messages": 0,
                    "methods": 0,
                    "misses": 5,
                    "partials": 0,
                    "sessions": 1,
                },
                "diff_totals": {
                    "branches": 0,
                    "complexity": 0,
                    "complexity_total": 0,
                    "complexity_ratio": 0,
                    "coverage": 0,
                    "diff": 0,
                    "files": 0,
                    "hits": 0,
                    "lines": 0,
                    "messages": 0,
                    "methods": 0,
                    "misses": 0,
                    "partials": 0,
                    "sessions": 0,
                },
                "head_report_totals": {
                    "branches": 0,
                    "complexity": 0,
                    "complexity_total": 0,
                    "complexity_ratio": 0,
                    "coverage": 80.00,
                    "diff": 0,
                    "files": 3,
                    "hits": 20,
                    "lines": 25,
                    "messages": 0,
                    "methods": 0,
                    "misses": 5,
                    "partials": 0,
                    "sessions": 1,
                },
            },
            {
                "name": "integrations",
                "base_report_totals": {
                    "branches": 0,
                    "complexity": 0,
                    "complexity_total": 0,
                    "complexity_ratio": 0,
                    "coverage": 79.17,
                    "diff": 0,
                    "files": 3,
                    "hits": 19,
                    "lines": 24,
                    "messages": 0,
                    "methods": 0,
                    "misses": 5,
                    "partials": 0,
                    "sessions": 1,
                },
                "diff_totals": {
                    "branches": 0,
                    "complexity": 0,
                    "complexity_total": 0,
                    "complexity_ratio": 0,
                    "coverage": 0,
                    "diff": 0,
                    "files": 0,
                    "hits": 0,
                    "lines": 0,
                    "messages": 0,
                    "methods": 0,
                    "misses": 0,
                    "partials": 0,
                    "sessions": 0,
                },
                "head_report_totals": {
                    "branches": 0,
                    "complexity": 0,
                    "complexity_total": 0,
                    "complexity_ratio": 0,
                    "coverage": 56.00,
                    "diff": 0,
                    "files": 3,
                    "hits": 14,
                    "lines": 25,
                    "messages": 0,
                    "methods": 0,
                    "misses": 11,
                    "partials": 0,
                    "sessions": 1,
                },
            },
        ]

        assert (
            response.data[0]["base_report_totals"]
            == expected_result[0]["base_report_totals"]
        )
        assert (
            response.data[0]["head_report_totals"]
            == expected_result[0]["head_report_totals"]
        )
        assert response.data[0] == expected_result[0]
        assert response.data[1] == expected_result[1]
        assert response.data == expected_result

    @patch("redis.Redis.get", lambda self, key: None)
    @patch("redis.Redis.set", lambda self, key, val, ex: None)
    def test_compare_flags_view_accepts_pullid_query_param(
        self, diff_totals_mock, read_chunks_mock, git_comparison_mock
    ):
        git_comparison_mock.return_value = {"diff": {"files": {}}}
        read_chunks_mock.return_value = ""
        diff_totals_mock.return_value = ReportTotals()

        response = self._get_compare_flags(
            kwargs={
                "service": self.repo.author.service,
                "owner_username": self.repo.author.username,
                "repo_name": self.repo.name,
            },
            query_params={
                "pullid": PullFactory(
                    base=self.parent_commit.commitid,
                    head=self.commit.commitid,
                    compared_to=self.parent_commit.commitid,
                    pullid=2,
                    author=self.commit.author,
                    repository=self.repo,
                ).pullid
            },
        )

        assert response.status_code == 200

    @patch("services.comparison.FlagComparison.base_report", new_callable=PropertyMock)
    def test_compare_flags_doesnt_crash_if_base_doesnt_have_flags(
        self, base_flag_mock, diff_totals_mock, read_chunks_mock, git_comparison_mock,
    ):
        git_comparison_mock.return_value = {"diff": {"files": {}}}
        read_chunks_mock.return_value = ""
        base_flag_mock.return_value = None
        diff_totals_mock.return_value = ReportTotals()

        # should not crash
        response = self._get_compare_flags(
            kwargs={
                "service": self.repo.author.service,
                "owner_username": self.repo.author.username,
                "repo_name": self.repo.name,
            },
            query_params={
                "base": self.parent_commit.commitid,
                "head": self.commit.commitid,
            },
        )

    @patch("shared.reports.resources.Report.totals", new_callable=PropertyMock)
    def test_compare_flags_view_doesnt_crash_if_coverage_is_none(
        self,
        report_totals_mock,
        diff_totals_mock,
        read_chunks_mock,
        git_comparison_mock,
    ):
        diff_totals_mock.return_value = ReportTotals()
        read_chunks_mock.return_value = ""
        git_comparison_mock.return_value = {"diff": {"files": {}}}
        report_totals_mock.return_value = ReportTotals(
            branches=0,
            complexity=0,
            complexity_total=0,
            coverage=None,
            diff=0,
            files=3,
            hits=19,
            lines=24,
            messages=0,
            methods=0,
            misses=5,
            partials=0,
            sessions=2,
        )

        # should not crash
        self._get_compare_flags(
            kwargs={
                "service": self.repo.author.service,
                "owner_username": self.repo.author.username,
                "repo_name": self.repo.name,
            },
            query_params={
                "base": self.parent_commit.commitid,
                "head": self.commit.commitid,
            },
        )
