import json
import re
from datetime import datetime
from unittest.mock import MagicMock, patch

import minio
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
        ProfilingCommitFactory(
            repository=self.repo,
            version_identifier="0.0.2",
            last_summarized_at=datetime(2022, 2, 1, 0, 0, 0),
        )
        pc = ProfilingCommitFactory(
            repository=self.repo,
            version_identifier="0.0.3",
            last_summarized_at=datetime(2022, 1, 1, 0, 0, 0),
        )
        ProfilingCommitFactory(
            repository=self.repo, version_identifier="0.0.4", last_summarized_at=None
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
        assert sorted(filenames) == ["app.py", "handlers.py"]

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

    def test_critical_files_from_yaml_no_profilingcommit_no_commitsha(self):
        critical_files_from_yaml = self.service._get_critical_files_from_yaml()
        assert critical_files_from_yaml == []

    @patch("services.profiling.UserYaml.get_final_yaml")
    @patch("services.profiling.ProfilingSummary.summary_data")
    @patch("services.profiling.ProfilingSummary.latest_profiling_commit")
    def test_critical_files_from_yaml_no_paths(
        self, latest_profiling_commit, summary_data, mocked_useryaml
    ):
        profiling_commit = ProfilingCommitFactory(
            repository=self.repo,
            last_summarized_at=datetime.now(),
            commit_sha="random_sha_thats_irrelevant_for_this_test",
        )
        latest_profiling_commit.return_value = profiling_commit
        summary_data.return_value = None
        mocked_useryaml.return_value = dict()
        critical_files_from_yaml = self.service._get_critical_files_from_yaml(
            profiling_commit
        )
        assert critical_files_from_yaml == []
        mocked_useryaml.assert_called_with(
            owner_yaml=self.repo.author.yaml,
            repo_yaml=self.repo.yaml,
            ownerid=self.repo.author.ownerid,
        )

    @patch("services.profiling.ReportService.build_report_from_commit")
    @patch("services.profiling.UserYaml.get_final_yaml")
    @patch("services.profiling.ProfilingSummary.summary_data")
    @patch("services.profiling.ProfilingSummary.latest_profiling_commit")
    def test_critical_files_from_yaml_no_report(
        self,
        latest_profiling_commit,
        summary_data,
        mocked_useryaml,
        mocked_reportservice,
    ):
        commit = CommitFactory(repository=self.repo)
        commit.save()
        profiling_commit = ProfilingCommitFactory(
            repository=self.repo,
            last_summarized_at=datetime.now(),
            commit_sha=commit.commitid,
        )
        latest_profiling_commit.return_value = profiling_commit
        summary_data.return_value = None
        mocked_useryaml.return_value = dict(
            profiling=dict(critical_files_paths=["batata.txt", "a.py"])
        )
        mocked_reportservice.return_value = None
        critical_files_from_yaml = self.service._get_critical_files_from_yaml(
            profiling_commit
        )
        assert critical_files_from_yaml == []
        mocked_useryaml.assert_called_with(
            owner_yaml=self.repo.author.yaml,
            repo_yaml=self.repo.yaml,
            ownerid=self.repo.author.ownerid,
        )
        mocked_reportservice.assert_called()

    @patch("services.profiling.ReportService.build_report_from_commit")
    @patch("services.profiling.UserYaml.get_final_yaml")
    @patch("services.profiling.ProfilingSummary.summary_data")
    @patch("services.profiling.ProfilingSummary.latest_profiling_commit")
    def test_critical_files_from_yaml_return_files(
        self,
        latest_profiling_commit,
        summary_data,
        mocked_useryaml,
        mocked_reportservice,
    ):
        commit = CommitFactory(repository=self.repo)
        commit.save()
        profiling_commit = ProfilingCommitFactory(
            repository=self.repo,
            last_summarized_at=datetime.now(),
            commit_sha=commit.commitid,
        )
        latest_profiling_commit.return_value = profiling_commit
        summary_data.return_value = None
        mocked_useryaml.return_value = dict(
            profiling=dict(critical_files_paths=["batata.txt", "src/critical"])
        )
        mock_report = MagicMock()
        mock_report.files = [
            "some_file.txt",
            "batata.txt",
            "src/critical/very_important.json",
        ]
        mocked_reportservice.return_value = mock_report

        critical_files_from_yaml = self.service._get_critical_files_from_yaml(
            profiling_commit
        )
        assert critical_files_from_yaml == [
            "batata.txt",
            "src/critical/very_important.json",
        ]
        mocked_useryaml.assert_called_with(
            owner_yaml=self.repo.author.yaml,
            repo_yaml=self.repo.yaml,
            ownerid=self.repo.author.ownerid,
        )
        mocked_reportservice.assert_called()

    @patch("services.profiling.ReportService.build_report_from_commit")
    @patch("services.profiling.UserYaml.get_final_yaml")
    @patch("services.profiling.ProfilingSummary.summary_data")
    @patch("services.profiling.ProfilingSummary.latest_profiling_commit")
    def test_critical_files_from_yaml_return_files_no_profiling_commit(
        self,
        latest_profiling_commit,
        summary_data,
        mocked_useryaml,
        mocked_reportservice,
    ):
        commit = CommitFactory(repository=self.repo)
        commit.save()
        self.service.commit_sha = commit.commitid
        latest_profiling_commit.return_value = None
        mocked_useryaml.return_value = dict(
            profiling=dict(critical_files_paths=["batata.txt", "src/critical"])
        )
        mock_report = MagicMock()
        mock_report.files = [
            "some_file.txt",
            "batata.txt",
            "src/critical/very_important.json",
        ]
        mocked_reportservice.return_value = mock_report

        critical_files_from_yaml = self.service._get_critical_files_from_yaml()
        assert critical_files_from_yaml == [
            "batata.txt",
            "src/critical/very_important.json",
        ]
        mocked_useryaml.assert_called()
        mocked_reportservice.assert_called()

    @patch("services.profiling.ReportService.build_report_from_commit")
    @patch("services.profiling.UserYaml.get_final_yaml")
    @patch("services.profiling.ProfilingSummary.summary_data")
    @patch("services.profiling.ProfilingSummary.latest_profiling_commit")
    def test_critical_files_from_yaml_and_profiling(
        self,
        latest_profiling_commit,
        summary_data,
        mocked_useryaml,
        mocked_reportservice,
    ):
        commit = CommitFactory(repository=self.repo)
        commit.save()
        profiling_commit = ProfilingCommitFactory(
            repository=self.repo,
            last_summarized_at=datetime.now(),
            commit_sha=commit.commitid,
        )
        latest_profiling_commit.return_value = profiling_commit
        summary_data.return_value = ProfilingSummaryDataAnalyzer(
            json.loads(test_summary)
        )
        mocked_useryaml.return_value = dict(
            profiling=dict(
                critical_files_paths=["batata.txt", "src/critical", "app.py"]
            )
        )
        mock_report = MagicMock()
        mock_report.files = [
            "some_file.txt",
            "batata.txt",
            "src/critical/very_important.json",
            "app.py",
        ]
        mocked_reportservice.return_value = mock_report

        filenames = [cf.name for cf in self.service.critical_files]
        assert sorted(filenames) == [
            "app.py",
            "batata.txt",
            "handlers.py",
            "src/critical/very_important.json",
        ]

    @patch("services.profiling.ReportService.build_report_from_commit")
    @patch("services.profiling.UserYaml.get_final_yaml")
    @patch("services.profiling.ProfilingSummary.summary_data")
    @patch("services.profiling.ProfilingSummary.latest_profiling_commit")
    def test_critical_files_no_profiling(
        self,
        latest_profiling_commit,
        summary_data,
        mocked_useryaml,
        mocked_reportservice,
    ):
        commit = CommitFactory(repository=self.repo)
        commit.save()
        self.service.commit_sha = commit.commitid
        latest_profiling_commit.return_value = None
        mocked_useryaml.return_value = dict(
            profiling=dict(
                critical_files_paths=["batata.txt", "src/critical", "app.py"]
            )
        )
        mock_report = MagicMock()
        mock_report.files = [
            "some_file.txt",
            "batata.txt",
            "src/critical/very_important.json",
            "app.py",
        ]
        mocked_reportservice.return_value = mock_report

        filenames = [cf.name for cf in self.service.critical_files]
        assert sorted(filenames) == [
            "app.py",
            "batata.txt",
            "src/critical/very_important.json",
        ]
        summary_data.assert_not_called()
