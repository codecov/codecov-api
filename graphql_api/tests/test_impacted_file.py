from unittest.mock import PropertyMock, patch

from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from compare.models import CommitComparison
from compare.tests.factories import CommitComparisonFactory
from core.tests.factories import CommitFactory, RepositoryFactory
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
          impactedFiles {
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
              header
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
        }
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
        ]
    }]
}
"""


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
                            "impactedFiles": [
                                {
                                    "headName": "fileA",
                                    "baseName": "fileA",
                                    "baseCoverage": {
                                        "percentCovered": 41.666666666666664
                                    },
                                    "headCoverage": {
                                        "percentCovered": 85.71428571428571
                                    },
                                    "patchCoverage": None,
                                },
                                {
                                    "headName": "fileB",
                                    "baseName": "fileB",
                                    "baseCoverage": {
                                        "percentCovered": 41.666666666666664
                                    },
                                    "headCoverage": {
                                        "percentCovered": 85.71428571428571
                                    },
                                    "patchCoverage": {"percentCovered": 100.0},
                                },
                            ]
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
                                "baseCoverage": {"percentCovered": 41.666666666666664},
                                "headCoverage": {"percentCovered": 85.71428571428571},
                                "patchCoverage": {"percentCovered": 100.0},
                                "segments": [],
                            }
                        }
                    }
                }
            }
        }
