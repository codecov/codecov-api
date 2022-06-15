from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TransactionTestCase
from shared.reports.types import LineSession

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import BranchFactory, CommitFactory, RepositoryFactory
from reports.tests.factories import CommitReportFactory

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
              name
              filePath
              percentCovered
              type
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
        self.totals = MockCoverage(83, 8, 10)


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


class TestCommit(GraphQLTestHelper, TransactionTestCase):
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
        query = query_branch % "name, head { commitid }"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
        }
        data = self.gql_request(query, variables=variables)
        branch = data["owner"]["repository"]["branch"]
        assert branch["name"] == self.branch.name
        assert branch["head"]["commitid"] == self.head.commitid

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

    @patch("core.models.ReportService.build_report_from_commit")
    def test_fetch_path_contents_with_files(self, report_mock):
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
            "path": "",
            "filters": {},
        }
        report_mock.return_value = MockReport()
        data = self.gql_request(query_files, variables=variables)

        expected_data = {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "pathContents": [
                                {
                                    "name": "fileA.py",
                                    "filePath": "fileA.py",
                                    "percentCovered": 83.0,
                                    "type": "file",
                                },
                                {
                                    "name": "fileB.py",
                                    "filePath": "fileB.py",
                                    "percentCovered": 83.0,
                                    "type": "file",
                                },
                                {
                                    "name": "folder",
                                    "filePath": None,
                                    "percentCovered": 80.0,
                                    "type": "dir",
                                },
                            ]
                        }
                    }
                }
            }
        }

        assert expected_data == data

    @patch("core.models.ReportService.build_report_from_commit")
    def test_fetch_path_contents_with_files_and_path_prefix(self, report_mock):
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
            "path": "folder",
            "filters": {},
        }
        report_mock.return_value = MockReport()
        data = self.gql_request(query_files, variables=variables)

        expected_data = {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "pathContents": [
                                {
                                    "name": "fileB.py",
                                    "filePath": "folder/fileB.py",
                                    "percentCovered": 83.0,
                                    "type": "file",
                                },
                                {
                                    "name": "subfolder",
                                    "filePath": None,
                                    "percentCovered": 80.0,
                                    "type": "dir",
                                },
                            ]
                        }
                    }
                }
            }
        }

        assert expected_data == data
