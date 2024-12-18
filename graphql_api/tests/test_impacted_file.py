import hashlib
from dataclasses import dataclass, field
from typing import Callable
from unittest.mock import PropertyMock, patch

from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import (
    CommitFactory,
    OwnerFactory,
    PullFactory,
    RepositoryFactory,
)
from shared.reports.resources import Report, ReportFile, ReportLine
from shared.torngit.exceptions import (
    TorngitClientGeneralError,
    TorngitObjectNotFoundError,
)
from shared.utils.sessions import Session

from compare.models import CommitComparison
from compare.tests.factories import CommitComparisonFactory
from services.comparison import ComparisonReport, ImpactedFile, MissingComparisonReport

from .helper import GraphQLTestHelper

query_impacted_files = """
query ImpactedFiles(
    $org: String!
    $repo: String!
    $commit: String!
) {
    owner(username: $org) {
        repository(name: $repo) {
            ... on Repository {
                commit(id: $commit) {
                    compareWithParent {
                        ... on Comparison {
                            impactedFilesCount
                            indirectChangedFilesCount
                            impactedFiles {
                                ... on ImpactedFiles {
                                    results {
                                        fileName
                                        headName
                                        baseName
                                        isNewFile
                                        isRenamedFile
                                        isDeletedFile
                                        isCriticalFile
                                        baseCoverage {
                                            percentCovered
                                        }
                                        headCoverage {
                                            percentCovered
                                        }
                                        patchCoverage {
                                            percentCovered
                                        }
                                        changeCoverage
                                            missesCount
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
"""

query_direct_changed_files_count = """
query ImpactedFiles(
    $org: String!
    $repo: String!
    $commit: String!
) {
    owner(username: $org) {
        repository(name: $repo) {
            ... on Repository {
                commit(id: $commit) {
                    compareWithParent {
                        ... on Comparison {
                            directChangedFilesCount
                        }
                    }
                }
            }
        }
    }
}
"""

query_impacted_file_through_pull = """
query ImpactedFile(
    $org: String!
    $repo: String!
    $pull: Int!
    $path: String!
    $filters: SegmentsFilters
) {
    owner(username: $org) {
        repository(name: $repo) {
            ... on Repository {
                pull(id: $pull) {
                    compareWithBase {
                        ... on Comparison {
                            state
                            impactedFile(path: $path) {
                                headName
                                baseName
                                hashedPath
                                baseCoverage {
                                    percentCovered
                                }
                                headCoverage {
                                    percentCovered
                                }
                                patchCoverage {
                                    percentCovered
                                }
                                segments(filters: $filters) {
                                    ... on SegmentComparisons {
                                        results {
                                            hasUnintendedChanges
                                        }
                                    }
                                    ... on ResolverError {
                                        message
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
"""
mock_data_from_archive = """
{
    "files": [{
        "head_name": "fileA",
        "base_name": "fileA",
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
            [10,"m"]
        ],
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
            [10,"h"],
            [13,"h"],
            [14,"h"],
            [15,"h"],
            [16,"m"],
            [17,"h"]
        ],
        "unexpected_line_changes": [[[1, "h"], [1, "m"]]]
    }]
}
"""


@dataclass
class MockSegment:
    has_diff_changes: bool = False
    has_unintended_changes: bool = False
    remove_unintended_changes: Callable[[], None] = field(default=lambda: None)


class MockFileComparison(object):
    def __init__(self):
        self.segments = [
            MockSegment(has_unintended_changes=True, has_diff_changes=False),
            MockSegment(has_unintended_changes=False, has_diff_changes=True),
            MockSegment(has_unintended_changes=True, has_diff_changes=True),
        ]


def sample_report():
    report = Report(flags={"flag1": True})
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
    third_file = ReportFile("file3.py")
    third_file.append(1, ReportLine.create(coverage=1, sessions=[[0, 1]]))
    report.append(first_file)
    report.append(second_file)
    report.append(third_file)
    report.add_session(Session(flags=["flag1"]))
    return report


class TestImpactedFileFiltering(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov")
        self.repo = RepositoryFactory(author=self.org, name="gazebo", private=False)
        self.author = OwnerFactory()
        self.parent_commit = CommitFactory(repository=self.repo)
        self.commit = CommitFactory(
            repository=self.repo,
            totals={"c": "12", "diff": [0, 0, 0, 0, 0, "14"]},
            parent_commit_id=self.parent_commit.commitid,
        )
        self.pull = PullFactory(
            pullid=44,
            repository=self.commit.repository,
            head=self.commit.commitid,
            base=self.parent_commit.commitid,
            compared_to=self.parent_commit.commitid,
        )
        self.comparison = CommitComparisonFactory(
            base_commit=self.parent_commit,
            compare_commit=self.commit,
            state=CommitComparison.CommitComparisonStates.PROCESSED,
            report_storage_path="v4/test.json",
        )
        self.comparison_report = ComparisonReport(self.comparison)

        self.query_impacted_files = """
            query ImpactedFiles(
                $org: String!
                $repo: String!
                $commit: String!
                $filters: ImpactedFilesFilters
            ) {
                owner(username: $org) {
                    repository(name: $repo) {
                        ... on Repository {
                            commit(id: $commit) {
                                compareWithParent {
                                    ... on Comparison {
                                        impactedFiles(filters: $filters) {
                                            ... on ImpactedFiles {
                                                results {
                                                    fileName
                                                }
                                            }
                                            ... on UnknownFlags {
                                                message
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        """

    @patch("shared.reports.api_report_service.build_report_from_commit")
    @patch("shared.api_archive.archive.ArchiveService.read_file")
    @patch("services.comparison.Comparison.git_comparison")
    def test_filtering_with_successful_flags(
        self, git_comparison_mock, read_file, build_report_from_commit
    ):
        git_comparison_mock.return_value = None
        build_report_from_commit.return_value = sample_report()
        read_file.return_value = mock_data_from_archive

        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
            "filters": {"flags": ["flag1"]},
        }

        data = self.gql_request(self.query_impacted_files, variables=variables)
        assert (
            "results"
            in data["owner"]["repository"]["commit"]["compareWithParent"][
                "impactedFiles"
            ]
        )

    @patch("shared.reports.api_report_service.build_report_from_commit")
    @patch("shared.api_archive.archive.ArchiveService.read_file")
    @patch("services.comparison.Comparison.git_comparison")
    def test_filtering_with_unknown_flags(
        self, git_comparison_mock, read_file, build_report_from_commit
    ):
        git_comparison_mock.return_value = None
        build_report_from_commit.return_value = sample_report()
        read_file.return_value = mock_data_from_archive

        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
            "filters": {"flags": ["fake_flag"]},
        }

        data = self.gql_request(self.query_impacted_files, variables=variables)
        assert data["owner"]["repository"]["commit"]["compareWithParent"][
            "impactedFiles"
        ] == {"message": "No coverage with chosen flags"}


class TestImpactedFile(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov")
        self.repo = RepositoryFactory(author=self.org, name="gazebo", private=False)
        self.author = OwnerFactory()
        self.parent_commit = CommitFactory(repository=self.repo)
        self.commit = CommitFactory(
            repository=self.repo,
            totals={"c": "12", "diff": [0, 0, 0, 0, 0, "14"]},
            parent_commit_id=self.parent_commit.commitid,
        )
        self.pull = PullFactory(
            pullid=44,
            repository=self.commit.repository,
            head=self.commit.commitid,
            base=self.parent_commit.commitid,
            compared_to=self.parent_commit.commitid,
        )
        self.comparison = CommitComparisonFactory(
            base_commit=self.parent_commit,
            compare_commit=self.commit,
            state=CommitComparison.CommitComparisonStates.PROCESSED,
            report_storage_path="v4/test.json",
        )
        self.comparison_report = ComparisonReport(self.comparison)

        # mock reports for all tests in this class
        self.head_report_patcher = patch(
            "services.comparison.Comparison.head_report", new_callable=PropertyMock
        )
        self.head_report = self.head_report_patcher.start()
        self.head_report.return_value = None
        self.addCleanup(self.head_report_patcher.stop)
        self.base_report_patcher = patch(
            "services.comparison.Comparison.base_report", new_callable=PropertyMock
        )
        self.base_report = self.base_report_patcher.start()
        self.base_report.return_value = None
        self.addCleanup(self.base_report_patcher.stop)

    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_fetch_impacted_files(self, read_file):
        read_file.return_value = mock_data_from_archive
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query_impacted_files, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "commit": {
                        "compareWithParent": {
                            "impactedFilesCount": 2,
                            "indirectChangedFilesCount": 1,
                            "impactedFiles": {
                                "results": [
                                    {
                                        "fileName": "fileA",
                                        "headName": "fileA",
                                        "baseName": "fileA",
                                        "isNewFile": False,
                                        "isRenamedFile": False,
                                        "isDeletedFile": False,
                                        "isCriticalFile": False,
                                        "baseCoverage": {
                                            "percentCovered": 41.666666666666664
                                        },
                                        "headCoverage": {
                                            "percentCovered": 85.71428571428571
                                        },
                                        "patchCoverage": {"percentCovered": 50.0},
                                        "changeCoverage": 44.047619047619044,
                                        "missesCount": 1,
                                    },
                                    {
                                        "fileName": "fileB",
                                        "headName": "fileB",
                                        "baseName": "fileB",
                                        "isNewFile": False,
                                        "isRenamedFile": False,
                                        "isDeletedFile": False,
                                        "isCriticalFile": False,
                                        "baseCoverage": {
                                            "percentCovered": 41.666666666666664
                                        },
                                        "headCoverage": {
                                            "percentCovered": 85.71428571428571
                                        },
                                        "patchCoverage": {
                                            "percentCovered": 85.71428571428571
                                        },
                                        "changeCoverage": 44.047619047619044,
                                        "missesCount": 2,
                                    },
                                ]
                            },
                        }
                    }
                }
            }
        }

    @patch("services.task.TaskService.compute_comparisons")
    @patch("services.comparison.ComparisonReport.impacted_file")
    @patch("services.comparison.Comparison.validate")
    @patch("services.comparison.PullRequestComparison.get_file_comparison")
    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_fetch_impacted_file_segments_without_comparison_in_context(
        self,
        read_file,
        mock_get_file_comparison,
        mock_compare_validate,
        mock_impacted_file,
        _,
    ):
        read_file.return_value = mock_data_from_archive
        mock_get_file_comparison.return_value = MockFileComparison()
        mock_compare_validate.return_value = True
        mock_impacted_file.return_value = ImpactedFile(
            **{
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
                    "methods": 5,
                },
                "base_coverage": {
                    "hits": 5,
                    "misses": 6,
                    "partials": 1,
                    "branches": 2,
                    "sessions": 0,
                    "complexity": 0,
                    "complexity_total": 0,
                    "methods": 4,
                },
                "added_diff_coverage": [
                    [9, "h"],
                    [10, "m"],
                    [13, "p"],
                    [14, "h"],
                    [15, "h"],
                    [16, "h"],
                    [17, "h"],
                ],
                "unexpected_line_changes": [[[1, "h"], [1, "h"]]],
            }
        )
        self.comparison.delete()
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "pull": self.pull.pullid,
            "path": "fileB",
        }
        data = self.gql_request(query_impacted_file_through_pull, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "pull": {
                        "compareWithBase": {
                            "state": "pending",
                            "impactedFile": {
                                "headName": "fileB",
                                "baseName": "fileB",
                                "hashedPath": "eea3f37743bfd3409bec556ab26d4698",
                                "baseCoverage": {"percentCovered": None},
                                "headCoverage": {"percentCovered": None},
                                "patchCoverage": {"percentCovered": 71.42857142857143},
                                "segments": {"results": []},
                            },
                        }
                    }
                }
            }
        }

    @patch("services.comparison.Comparison.validate")
    @patch("services.comparison.PullRequestComparison.get_file_comparison")
    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_fetch_impacted_file_with_segments(
        self, read_file, mock_get_file_comparison, mock_compare_validate
    ):
        read_file.return_value = mock_data_from_archive

        mock_get_file_comparison.return_value = MockFileComparison()
        mock_compare_validate.return_value = True
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "pull": self.pull.pullid,
            "path": "fileB",
        }
        data = self.gql_request(query_impacted_file_through_pull, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "pull": {
                        "compareWithBase": {
                            "state": "processed",
                            "impactedFile": {
                                "headName": "fileB",
                                "baseName": "fileB",
                                "hashedPath": hashlib.md5("fileB".encode()).hexdigest(),
                                "baseCoverage": {"percentCovered": 41.666666666666664},
                                "headCoverage": {"percentCovered": 85.71428571428571},
                                "patchCoverage": {"percentCovered": 85.71428571428571},
                                "segments": {
                                    "results": [
                                        {"hasUnintendedChanges": True},
                                        {"hasUnintendedChanges": False},
                                        {"hasUnintendedChanges": True},
                                    ],
                                },
                            },
                        }
                    }
                }
            }
        }

    @patch("services.comparison.Comparison.validate")
    @patch("services.comparison.PullRequestComparison.get_file_comparison")
    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_fetch_impacted_file_segments_with_indirect_and_direct_changes(
        self, read_file, mock_get_file_comparison, mock_compare_validate
    ):
        read_file.return_value = mock_data_from_archive

        mock_get_file_comparison.return_value = MockFileComparison()
        mock_compare_validate.return_value = True
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "pull": self.pull.pullid,
            "path": "fileA",
            "filters": {"hasUnintendedChanges": True},
        }
        data = self.gql_request(query_impacted_file_through_pull, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "pull": {
                        "compareWithBase": {
                            "state": "processed",
                            "impactedFile": {
                                "headName": "fileA",
                                "baseName": "fileA",
                                "hashedPath": "5e9f0c9689fb7ec181ea0fb09ad3f74e",
                                "baseCoverage": {"percentCovered": 41.666666666666664},
                                "headCoverage": {"percentCovered": 85.71428571428571},
                                "patchCoverage": {"percentCovered": 50.0},
                                "segments": {
                                    "results": [
                                        {"hasUnintendedChanges": True},
                                        {"hasUnintendedChanges": True},
                                    ]
                                },
                            },
                        }
                    }
                }
            }
        }

    @patch("services.comparison.Comparison.validate")
    @patch("services.comparison.PullRequestComparison.get_file_comparison")
    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_fetch_impacted_file_with_segments_unknown_path(
        self, read_file, mock_get_file_comparison, mock_compare_validate
    ):
        read_file.return_value = mock_data_from_archive
        mock_get_file_comparison.side_effect = TorngitObjectNotFoundError(None, None)
        mock_compare_validate.return_value = True

        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "pull": self.pull.pullid,
            "path": "fileA",
        }
        data = self.gql_request(query_impacted_file_through_pull, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "pull": {
                        "compareWithBase": {
                            "state": "processed",
                            "impactedFile": {
                                "headName": "fileA",
                                "baseName": "fileA",
                                "hashedPath": hashlib.md5("fileA".encode()).hexdigest(),
                                "baseCoverage": {"percentCovered": 41.666666666666664},
                                "headCoverage": {"percentCovered": 85.71428571428571},
                                "patchCoverage": {"percentCovered": 50.0},
                                "segments": {"message": "path does not exist: fileA"},
                            },
                        }
                    }
                }
            }
        }

    @patch("services.comparison.Comparison.validate")
    @patch("services.comparison.PullRequestComparison.get_file_comparison")
    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_fetch_impacted_file_with_segments_provider_error(
        self, read_file, mock_get_file_comparison, mock_compare_validate
    ):
        read_file.return_value = mock_data_from_archive
        mock_get_file_comparison.side_effect = TorngitClientGeneralError(
            500, None, None
        )
        mock_compare_validate.return_value = True

        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "pull": self.pull.pullid,
            "path": "fileA",
        }
        data = self.gql_request(query_impacted_file_through_pull, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "pull": {
                        "compareWithBase": {
                            "state": "processed",
                            "impactedFile": {
                                "headName": "fileA",
                                "baseName": "fileA",
                                "hashedPath": hashlib.md5("fileA".encode()).hexdigest(),
                                "baseCoverage": {"percentCovered": 41.666666666666664},
                                "headCoverage": {"percentCovered": 85.71428571428571},
                                "patchCoverage": {"percentCovered": 50.0},
                                "segments": {
                                    "message": "Error fetching data from the provider"
                                },
                            },
                        }
                    }
                }
            }
        }

    @patch("services.comparison.Comparison.validate")
    @patch("services.comparison.PullRequestComparison.get_file_comparison")
    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_fetch_impacted_file_with_invalid_comparison(
        self, read_file, mock_get_file_comparison, mock_compare_validate
    ):
        read_file.return_value = mock_data_from_archive

        mock_get_file_comparison.return_value = MockFileComparison()
        mock_compare_validate.side_effect = MissingComparisonReport()
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "pull": self.pull.pullid,
            "path": "fileA",
            "filters": {"hasUnintendedChanges": False},
        }
        data = self.gql_request(query_impacted_file_through_pull, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "pull": {
                        "compareWithBase": {
                            "state": "processed",
                            "impactedFile": {
                                "headName": "fileA",
                                "baseName": "fileA",
                                "hashedPath": "5e9f0c9689fb7ec181ea0fb09ad3f74e",
                                "baseCoverage": {"percentCovered": 41.666666666666664},
                                "headCoverage": {"percentCovered": 85.71428571428571},
                                "patchCoverage": {"percentCovered": 50.0},
                                "segments": {"results": []},
                            },
                        }
                    }
                }
            }
        }

    @patch("services.comparison.Comparison.validate")
    @patch("services.comparison.PullRequestComparison.get_file_comparison")
    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_fetch_impacted_file_segments_with_direct_and_indirect_changes(
        self, read_file, mock_get_file_comparison, mock_compare_validate
    ):
        read_file.return_value = mock_data_from_archive

        mock_get_file_comparison.return_value = MockFileComparison()
        mock_compare_validate.return_value = True
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "pull": self.pull.pullid,
            "path": "fileA",
            "filters": {"hasUnintendedChanges": False},
        }
        data = self.gql_request(query_impacted_file_through_pull, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "pull": {
                        "compareWithBase": {
                            "state": "processed",
                            "impactedFile": {
                                "headName": "fileA",
                                "baseName": "fileA",
                                "hashedPath": "5e9f0c9689fb7ec181ea0fb09ad3f74e",
                                "baseCoverage": {"percentCovered": 41.666666666666664},
                                "headCoverage": {"percentCovered": 85.71428571428571},
                                "patchCoverage": {"percentCovered": 50.0},
                                "segments": {
                                    "results": [
                                        {"hasUnintendedChanges": False},
                                        {"hasUnintendedChanges": True},
                                    ]
                                },
                            },
                        }
                    }
                }
            }
        }

    @patch("services.comparison.Comparison.validate")
    @patch("services.comparison.PullRequestComparison.get_file_comparison")
    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_fetch_impacted_file_without_segments_filter(
        self, read_file, mock_get_file_comparison, mock_compare_validate
    ):
        read_file.return_value = mock_data_from_archive

        mock_get_file_comparison.return_value = MockFileComparison()
        mock_compare_validate.return_value = True
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "pull": self.pull.pullid,
            "path": "fileA",
        }
        data = self.gql_request(query_impacted_file_through_pull, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "pull": {
                        "compareWithBase": {
                            "state": "processed",
                            "impactedFile": {
                                "headName": "fileA",
                                "baseName": "fileA",
                                "hashedPath": "5e9f0c9689fb7ec181ea0fb09ad3f74e",
                                "baseCoverage": {"percentCovered": 41.666666666666664},
                                "headCoverage": {"percentCovered": 85.71428571428571},
                                "patchCoverage": {"percentCovered": 50.0},
                                "segments": {
                                    "results": [
                                        {"hasUnintendedChanges": True},
                                        {"hasUnintendedChanges": False},
                                        {"hasUnintendedChanges": True},
                                    ]
                                },
                            },
                        }
                    }
                }
            }
        }

    @patch("shared.api_archive.archive.ArchiveService.read_file")
    def test_fetch_direct_changed_files_count(self, read_file):
        read_file.return_value = mock_data_from_archive
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(
            query_direct_changed_files_count,
            variables=variables,
        )
        assert data == {
            "owner": {
                "repository": {
                    "commit": {
                        "compareWithParent": {
                            "directChangedFilesCount": 2,
                        }
                    }
                }
            }
        }
