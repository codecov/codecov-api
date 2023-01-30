import hashlib
from unittest.mock import PropertyMock, patch

from django.test import TransactionTestCase
from shared.torngit.exceptions import (
    TorngitClientGeneralError,
    TorngitObjectNotFoundError,
)

from codecov_auth.tests.factories import OwnerFactory
from compare.models import CommitComparison
from compare.tests.factories import CommitComparisonFactory
from core.tests.factories import CommitFactory, PullFactory, RepositoryFactory
from services.comparison import ComparisonReport

from .helper import GraphQLTestHelper

query_impacted_files = """
query ImpactedFiles(
    $org: String!
    $repo: String!
    $commit: String!
) {
  owner(username: $org) {
    repository(name: $repo) {
      commit(id: $commit) {
        compareWithParent {
          impactedFilesCount
          indirectChangedFilesCount
          impactedFiles {
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
          }
        }
      }
    }
  }
}
"""

query_impacted_file = """
query ImpactedFile(
    $org: String!
    $repo: String!
    $commit: String!
    $path: String!
) {
  owner(username: $org) {
    repository(name: $repo) {
      commit(id: $commit) {
        compareWithParent {
          impactedFile(path: $path) {
            hashedPath
            headName
            baseName
            baseCoverage {
              percentCovered
            }
            headCoverage {
              percentCovered
            }
            patchCoverage {
              percentCovered
            }
            segments {
              ... on SegmentComparisons {
                results {
                  hasUnintendedChanges
                }
              }
              ... on ResolverError {
                message
              }
            }
            missesInComparison
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
            [16,"h"],
            [17,"h"]
        ],
        "unexpected_line_changes": [[[1, "h"], [1, "m"]]]
    }]
}
"""


class MockSegmentWithNoUnexpectedChanges(object):
    def __init__(self):
        self.has_unintended_changes = False


class MockSegmentWithUnintendedChanges(object):
    def __init__(self):
        self.has_unintended_changes = True


class MockFileComparison(object):
    def __init__(self):
        self.segments = [
            MockSegmentWithUnintendedChanges(),
            MockSegmentWithNoUnexpectedChanges(),
        ]


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

    @patch("services.archive.ArchiveService.read_file")
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
                            "impactedFiles": [
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
                                    "patchCoverage": {"percentCovered": 100.0},
                                    "changeCoverage": 44.047619047619044,
                                },
                            ],
                        }
                    }
                }
            }
        }

    @patch("services.archive.ArchiveService.read_file")
    def test_fetch_impacted_files_count(self, read_file):
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
                            "impactedFiles": [
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
                                    "patchCoverage": {"percentCovered": 100.0},
                                    "changeCoverage": 44.047619047619044,
                                },
                            ],
                        }
                    }
                }
            }
        }

    @patch("services.archive.ArchiveService.read_file")
    def test_fetch_impacted_file_without_segments(self, read_file):
        read_file.return_value = mock_data_from_archive
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
            "path": "fileB",
        }
        data = self.gql_request(query_impacted_file, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "commit": {
                        "compareWithParent": {
                            "impactedFile": {
                                "headName": "fileB",
                                "baseName": "fileB",
                                "hashedPath": hashlib.md5("fileB".encode()).hexdigest(),
                                "baseCoverage": {"percentCovered": 41.666666666666664},
                                "headCoverage": {"percentCovered": 85.71428571428571},
                                "patchCoverage": {"percentCovered": 100.0},
                                "segments": {
                                    "message": "cannot query segments in this context"
                                },
                                "missesInComparison": 1,
                            }
                        }
                    }
                }
            }
        }

    @patch("services.comparison.Comparison.validate")
    @patch("services.comparison.PullRequestComparison.get_file_comparison")
    @patch("services.archive.ArchiveService.read_file")
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
                                "patchCoverage": {"percentCovered": 100.0},
                                "segments": {
                                    "results": [
                                        {"hasUnintendedChanges": True},
                                        {"hasUnintendedChanges": False},
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
    @patch("services.archive.ArchiveService.read_file")
    def test_fetch_impacted_file_with_segments_filter(
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
                                "hashedPath": hashlib.md5("fileA".encode()).hexdigest(),
                                "baseCoverage": {"percentCovered": 41.666666666666664},
                                "headCoverage": {"percentCovered": 85.71428571428571},
                                "patchCoverage": {"percentCovered": 50.0},
                                "segments": {
                                    "results": [{"hasUnintendedChanges": True}],
                                },
                            },
                        }
                    }
                }
            }
        }

    @patch("services.comparison.Comparison.validate")
    @patch("services.comparison.PullRequestComparison.get_file_comparison")
    @patch("services.archive.ArchiveService.read_file")
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
    @patch("services.archive.ArchiveService.read_file")
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
    @patch("services.archive.ArchiveService.read_file")
    def test_fetch_impacted_file_with_segments_filter_set_to_false(
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
                                    "results": [{"hasUnintendedChanges": False}]
                                },
                            },
                        }
                    }
                }
            }
        }

    @patch("services.comparison.Comparison.validate")
    @patch("services.comparison.PullRequestComparison.get_file_comparison")
    @patch("services.archive.ArchiveService.read_file")
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
        print(data)
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
                                    ]
                                },
                            },
                        }
                    }
                }
            }
        }
