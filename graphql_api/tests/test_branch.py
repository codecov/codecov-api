from datetime import datetime, timedelta
from unittest.mock import PropertyMock, patch

from django.test import TransactionTestCase, override_settings
from shared.reports.types import ReportTotals

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import BranchFactory, CommitFactory, RepositoryFactory
from services.profiling import CriticalFile

from .helper import GraphQLTestHelper

query_branch = """
query FetchBranch($org: String!, $repo: String!, $branch: String!) {
  owner(username: $org) {
    repository(name: $repo) {
      branch(name: $branch) {
        %s
      }
    }
  }
}
"""

query_files = """
  query FetchFiles($org: String!, $repo: String!, $branch: String!, $path: String!, $filters: PathContentsFilters!) {
    owner(username: $org) {
      repository(name: $repo) {
        branch(name: $branch) {
          head {
            pathContents (path: $path, filters: $filters) {
              __typename
              name
              path
              hits
              misses
              partials
              lines
              percentCovered
              ... on PathContentFile {
                isCriticalFile
              }
            }
          }
        }
      }
    }
  }
"""


class MockCoverage(object):
    def __init__(self, coverage, hits, lines):
        self.coverage = coverage
        self.hits = hits
        self.lines = lines


class MockTotals(object):
    def __init__(self):
        self.totals = ReportTotals.default_totals()
        self.totals.hits = 8
        self.totals.lines = 10


class MockReport(object):
    def get(self, file):
        return MockTotals()

    @property
    def files(self):
        return [
            "fileA.py",
            "fileB.py",
            "folder/fileB.py",
            "folder/subfolder/fileC.py",
            "folder/subfolder/fileD.py",
        ]


class TestBranch(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov")
        self.repo = RepositoryFactory(author=self.org, name="gazebo", private=False)
        self.head = CommitFactory(repository=self.repo, timestamp=datetime.now())
        self.commit = CommitFactory(repository=self.repo)
        self.branch = BranchFactory(
            repository=self.repo,
            head=self.head.commitid,
            name="test1",
            updatestamp=(datetime.now() + timedelta(1)),
        )
        self.branch_2 = BranchFactory(
            repository=self.repo,
            head=self.commit.commitid,
            name="test2",
            updatestamp=(datetime.now() + timedelta(2)),
        )

    def test_fetch_branch(self):
        query = query_branch % "name, headSha, head { commitid }"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
        }
        data = self.gql_request(query, variables=variables)
        assert data["owner"]["repository"]["branch"] == {
            "name": self.branch.name,
            "headSha": self.head.commitid,
            "head": {
                "commitid": self.head.commitid,
            },
        }

    def test_fetch_branch_missing_commit(self):
        self.head.delete()
        query = query_branch % "name, headSha, head { commitid }"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
        }
        data = self.gql_request(query, variables=variables)
        assert data["owner"]["repository"]["branch"] == {
            "name": self.branch.name,
            "headSha": self.branch.head,
            "head": None,
        }

    def test_fetch_branches(self):
        query_branches = """{
            owner(username: "%s") {
              repository(name: "%s") {
                branches{
                  edges{
                    node{
                      name
                    }
                  }
                }
              }
            }
        }
        """
        variables = {"org": self.org.username, "repo": self.repo.name}
        query = query_branches % (self.org.username, self.repo.name)
        data = self.gql_request(query, variables=variables)
        branches = data["owner"]["repository"]["branches"]["edges"]
        assert type(branches) == list
        assert len(branches) == 3
        assert branches == [
            {"node": {"name": "test2"}},
            {"node": {"name": "test1"}},
            {"node": {"name": "master"}},
        ]

    @override_settings(DEBUG=True)
    def test_fetch_path_contents_with_no_report(self):
        commit_without_report = CommitFactory(repository=self.repo, report=None)
        branch = BranchFactory(
            repository=self.repo,
            head=commit_without_report.commitid,
            name="branch-two",
            updatestamp=(datetime.now() + timedelta(1)),
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": branch.name,
            "path": "",
            "filters": {},
        }
        res = self.gql_request(query_files, variables=variables, with_errors=True)
        assert res["errors"] is not None
        assert res["errors"][0]["message"] == "No reports found in the head commit"

    @patch(
        "services.profiling.ProfilingSummary.critical_files", new_callable=PropertyMock
    )
    @patch("core.models.ReportService.build_report_from_commit")
    def test_fetch_path_contents_with_files(self, report_mock, critical_files):
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
            "path": "",
            "filters": {
                "ordering": {
                    "direction": "DESC",
                    "parameter": "NAME",
                }
            },
        }
        report_mock.return_value = MockReport()
        critical_files.return_value = [CriticalFile("fileA.py")]

        data = self.gql_request(query_files, variables=variables)

        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "pathContents": [
                                {
                                    "__typename": "PathContentDir",
                                    "name": "folder",
                                    "path": "folder",
                                    "hits": 24,
                                    "misses": 0,
                                    "partials": 0,
                                    "lines": 30,
                                    "percentCovered": 80.0,
                                },
                                {
                                    "__typename": "PathContentFile",
                                    "name": "fileB.py",
                                    "path": "fileB.py",
                                    "hits": 8,
                                    "misses": 0,
                                    "partials": 0,
                                    "lines": 10,
                                    "percentCovered": 80.0,
                                    "isCriticalFile": False,
                                },
                                {
                                    "__typename": "PathContentFile",
                                    "name": "fileA.py",
                                    "path": "fileA.py",
                                    "hits": 8,
                                    "misses": 0,
                                    "partials": 0,
                                    "lines": 10,
                                    "percentCovered": 80.0,
                                    "isCriticalFile": True,
                                },
                            ]
                        }
                    }
                }
            }
        }

    @patch(
        "services.profiling.ProfilingSummary.critical_files", new_callable=PropertyMock
    )
    @patch("core.models.ReportService.build_report_from_commit")
    def test_fetch_path_contents_with_files_and_path_prefix(
        self, report_mock, critical_files
    ):
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
            "path": "folder",
            "filters": {
                "ordering": {
                    "direction": "ASC",
                    "parameter": "HITS",
                }
            },
        }
        report_mock.return_value = MockReport()
        critical_files.return_value = [CriticalFile("folder/fileB.py")]

        data = self.gql_request(query_files, variables=variables)

        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "pathContents": [
                                {
                                    "__typename": "PathContentFile",
                                    "name": "fileB.py",
                                    "path": "folder/fileB.py",
                                    "hits": 8,
                                    "misses": 0,
                                    "partials": 0,
                                    "lines": 10,
                                    "percentCovered": 80.0,
                                    "isCriticalFile": True,
                                },
                                {
                                    "__typename": "PathContentDir",
                                    "name": "subfolder",
                                    "path": "folder/subfolder",
                                    "hits": 16,
                                    "misses": 0,
                                    "partials": 0,
                                    "lines": 20,
                                    "percentCovered": 80.0,
                                },
                            ]
                        }
                    }
                }
            }
        }

    @patch(
        "services.profiling.ProfilingSummary.critical_files", new_callable=PropertyMock
    )
    @patch("core.models.ReportService.build_report_from_commit")
    def test_fetch_path_contents_with_files_and_search_value(
        self, report_mock, critical_files
    ):
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
            "path": "",
            "filters": {
                "searchValue": "fileB",
            },
        }
        report_mock.return_value = MockReport()
        critical_files.return_value = [CriticalFile("folder/fileB.py")]

        data = self.gql_request(query_files, variables=variables)

        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "pathContents": [
                                {
                                    "__typename": "PathContentFile",
                                    "name": "fileB.py",
                                    "path": "fileB.py",
                                    "hits": 8,
                                    "misses": 0,
                                    "partials": 0,
                                    "lines": 10,
                                    "percentCovered": 80.0,
                                    "isCriticalFile": False,
                                },
                                {
                                    "__typename": "PathContentFile",
                                    "name": "fileB.py",
                                    "path": "folder/fileB.py",
                                    "hits": 8,
                                    "misses": 0,
                                    "partials": 0,
                                    "lines": 10,
                                    "percentCovered": 80.0,
                                    "isCriticalFile": True,
                                },
                            ]
                        }
                    }
                }
            }
        }

    @patch("core.models.ReportService.build_report_from_commit")
    def test_fetch_path_contents_with_files_and_list_display_type(self, report_mock):
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
            "path": "",
            "filters": {
                "displayType": "LIST",
            },
        }
        report_mock.return_value = MockReport()

        data = self.gql_request(query_files, variables=variables)

        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "pathContents": [
                                {
                                    "__typename": "PathContentFile",
                                    "name": "fileA.py",
                                    "path": "fileA.py",
                                    "hits": 8,
                                    "misses": 0,
                                    "partials": 0,
                                    "lines": 10,
                                    "percentCovered": 80.0,
                                    "isCriticalFile": False,
                                },
                                {
                                    "__typename": "PathContentFile",
                                    "name": "fileB.py",
                                    "path": "fileB.py",
                                    "hits": 8,
                                    "misses": 0,
                                    "partials": 0,
                                    "lines": 10,
                                    "percentCovered": 80.0,
                                    "isCriticalFile": False,
                                },
                                {
                                    "__typename": "PathContentFile",
                                    "name": "fileB.py",
                                    "path": "folder/fileB.py",
                                    "hits": 8,
                                    "misses": 0,
                                    "partials": 0,
                                    "lines": 10,
                                    "percentCovered": 80.0,
                                    "isCriticalFile": False,
                                },
                                {
                                    "__typename": "PathContentFile",
                                    "name": "fileC.py",
                                    "path": "folder/subfolder/fileC.py",
                                    "hits": 8,
                                    "misses": 0,
                                    "partials": 0,
                                    "lines": 10,
                                    "percentCovered": 80.0,
                                    "isCriticalFile": False,
                                },
                                {
                                    "__typename": "PathContentFile",
                                    "name": "fileD.py",
                                    "path": "folder/subfolder/fileD.py",
                                    "hits": 8,
                                    "misses": 0,
                                    "partials": 0,
                                    "lines": 10,
                                    "percentCovered": 80.0,
                                    "isCriticalFile": False,
                                },
                            ]
                        }
                    }
                }
            }
        }
        assert len(
            data["owner"]["repository"]["branch"]["head"]["pathContents"]
        ) == len(report_mock.return_value.files)
