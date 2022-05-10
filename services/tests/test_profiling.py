import json
from datetime import datetime
from unittest.mock import patch

import minio
import pytest
from django.test import TestCase
from shared.profiling import ProfilingSummaryDataAnalyzer

from core.tests.factories import CommitFactory, RepositoryFactory
from profiling.tests.factories import ProfilingCommitFactory
from services.profiling import ProfilingSummary

test_summary = """
{
    "version": "v1",
    "general": {
        "total_profiled_files": 2
    },
    "file_groups": {
        "sum_of_executions": {
            "top_10_percent": [
                "app.py",
                "handlers.py"
            ],
            "above_1_stdev": [
                "app.py",
                "handlers.py"
            ]
            },
            "max_number_of_executions": {
            "top_10_percent": [
                "app.py",
                "handlers.py"
            ],
            "above_1_stdev": [
                "app.py",
                "handlers.py"
            ]
            },
            "avg_number_of_executions": {
            "top_10_percent": [
                "app.py",
                "handlers.py"
            ],
            "above_1_stdev": [
                "app.py",
                "handlers.py"
            ]
        }
    }
}
"""


class ProfilingSummaryTests(TestCase):
    def setUp(self):
        self.repo = RepositoryFactory()
        self.service = ProfilingSummary(self.repo)

    def test_latest_profiling_commit(self):
        ProfilingCommitFactory(repository=self.repo, version_identifier="0.0.1")
        pc = ProfilingCommitFactory(
            repository=self.repo,
            version_identifier="0.0.3",
            last_summarized_at=datetime(2022, 2, 1, 0, 0, 0),
        )
        ProfilingCommitFactory(
            repository=self.repo,
            version_identifier="0.0.2",
            last_summarized_at=datetime(2022, 1, 1, 0, 0, 0),
        )
        ProfilingCommitFactory(last_summarized_at=datetime(2022, 3, 1, 0, 0, 0))

        assert self.service.latest_profiling_commit() == pc

    def test_latest_profiling_commit_with_sha(self):
        commit1 = CommitFactory(repository=self.repo)
        commit2 = CommitFactory(repository=self.repo)

        ProfilingCommitFactory(repository=self.repo, version_identifier="0.0.1")
        ProfilingCommitFactory(
            repository=self.repo,
            version_identifier="0.0.2",
            last_summarized_at=datetime(2022, 1, 1, 0, 0, 0),
            commit_sha=commit1.commitid,
        )
        pc = ProfilingCommitFactory(
            repository=self.repo,
            version_identifier="0.0.3",
            last_summarized_at=datetime(2022, 2, 1, 0, 0, 0),
            commit_sha=commit1.commitid,
        )
        ProfilingCommitFactory(
            repository=self.repo,
            version_identifier="0.0.4",
            last_summarized_at=datetime(2022, 3, 1, 0, 0, 0),
            commit_sha=commit2.commitid,
        )
        ProfilingCommitFactory(last_summarized_at=datetime(2022, 4, 1, 0, 0, 0))

        service = ProfilingSummary(self.repo, commit_sha=commit1.commitid)
        assert service.latest_profiling_commit() == pc

    def test_summary_data_not_summarized(self):
        pc = ProfilingCommitFactory(repository=self.repo)
        assert self.service.summary_data(pc) == None

    @patch("services.archive.ArchiveService.read_file")
    def test_summary_data_not_found(self, read_file):
        read_file.side_effect = [minio.error.NoSuchKey]

        pc = ProfilingCommitFactory(
            repository=self.repo,
            last_summarized_at=datetime.now(),
        )

        assert self.service.summary_data(pc) == None

    @patch("services.archive.ArchiveService.read_file")
    def test_summary_data(self, read_file):
        read_file.return_value = test_summary
        pc = ProfilingCommitFactory(
            repository=self.repo,
            last_summarized_at=datetime.now(),
        )

        res = self.service.summary_data(pc)
        assert isinstance(res, ProfilingSummaryDataAnalyzer)

        expected = ProfilingSummaryDataAnalyzer(json.loads(test_summary))
        assert (
            res.get_critical_files_filenames()
            == expected.get_critical_files_filenames()
        )

    @patch("services.profiling.ProfilingSummary.summary_data")
    @patch("services.profiling.ProfilingSummary.latest_profiling_commit")
    def test_critical_files(self, latest_profiling_commit, summary_data):
        latest_profiling_commit.return_value = ProfilingCommitFactory(
            repository=self.repo,
            last_summarized_at=datetime.now(),
        )
        summary_data.return_value = ProfilingSummaryDataAnalyzer(
            json.loads(test_summary)
        )

        filenames = [cf.name for cf in self.service.critical_files]
        assert filenames == ["app.py", "handlers.py"]

    @patch("services.profiling.ProfilingSummary.summary_data")
    @patch("services.profiling.ProfilingSummary.latest_profiling_commit")
    def test_critical_files_no_profiling_commit(
        self, latest_profiling_commit, summary_data
    ):
        latest_profiling_commit.return_value = None
        summary_data.return_value = ProfilingSummaryDataAnalyzer(
            json.loads(test_summary)
        )

        assert self.service.critical_files == []

    @patch("services.profiling.ProfilingSummary.summary_data")
    @patch("services.profiling.ProfilingSummary.latest_profiling_commit")
    def test_critical_files_no_summary_data(
        self, latest_profiling_commit, summary_data
    ):
        latest_profiling_commit.return_value = ProfilingCommitFactory(
            repository=self.repo,
            last_summarized_at=datetime.now(),
        )
        summary_data.return_value = None

        assert self.service.critical_files == []
