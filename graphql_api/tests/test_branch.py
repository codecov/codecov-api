from datetime import datetime, timedelta
from unittest.mock import PropertyMock, patch

from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import BranchFactory, CommitFactory, RepositoryFactory
from reports.tests.factories import RepositoryFlagFactory
from services.profiling import CriticalFile
from timeseries.tests.factories import MeasurementFactory

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

query_flags = """
query Flags(
    $org: String!
    $repo: String!
    $branch: String!
    $before: DateTime!
) {
    owner(username: $org) {
        repository(name: $repo) {
            branch(name: $branch) {
                flags {
                    edges {
                        node {
                            ...FlagFragment
                        }
                    }
                }
            }
        }
    }
}

fragment FlagFragment on Flag {
    name
    percentCovered
    measurements(
        interval: INTERVAL_1_DAY
        after: "2000-01-01T00:00:00",
        before: $before
    ) {
        timestamp
        avg
        min
        max
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


class TestBranch(GraphQLTestHelper, TransactionTestCase):
    databases = {"default", "timeseries"}

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
            "filters": {},
        }
        report_mock.return_value = MockReport()
        critical_files.return_value = [CriticalFile("fileA.py")]

        data = self.gql_request(query_files, variables=variables)

        expected_data = {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "pathContents": [
                                {
                                    "__typename": "PathContentFile",
                                    "name": "fileA.py",
                                    "path": "fileA.py",
                                    "percentCovered": 83.0,
                                    "isCriticalFile": True,
                                },
                                {
                                    "__typename": "PathContentFile",
                                    "name": "fileB.py",
                                    "path": "fileB.py",
                                    "percentCovered": 83.0,
                                    "isCriticalFile": False,
                                },
                                {
                                    "__typename": "PathContentDir",
                                    "name": "folder",
                                    "path": None,
                                    "percentCovered": 80.0,
                                },
                            ]
                        }
                    }
                }
            }
        }

        assert expected_data == data

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
            "filters": {},
        }
        report_mock.return_value = MockReport()
        critical_files.return_value = [CriticalFile("folder/fileB.py")]

        data = self.gql_request(query_files, variables=variables)

        expected_data = {
            "owner": {
                "repository": {
                    "branch": {
                        "head": {
                            "pathContents": [
                                {
                                    "__typename": "PathContentFile",
                                    "name": "fileB.py",
                                    "path": "folder/fileB.py",
                                    "percentCovered": 83.0,
                                    "isCriticalFile": True,
                                },
                                {
                                    "__typename": "PathContentDir",
                                    "name": "subfolder",
                                    "path": None,
                                    "percentCovered": 80.0,
                                },
                            ]
                        }
                    }
                }
            }
        }

        assert expected_data == data

    def test_fetch_flags_no_measurements(self):
        flag1 = RepositoryFlagFactory(repository=self.repo, flag_name="flag1")
        flag2 = RepositoryFlagFactory(repository=self.repo, flag_name="flag2")
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
            "before": timezone.now().isoformat(),
        }
        data = self.gql_request(query_flags, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "flags": {
                            "edges": [
                                {
                                    "node": {
                                        "name": "flag1",
                                        "percentCovered": None,
                                        "measurements": [],
                                    }
                                },
                                {
                                    "node": {
                                        "name": "flag2",
                                        "percentCovered": None,
                                        "measurements": [],
                                    }
                                },
                            ]
                        }
                    }
                }
            }
        }

    def test_fetch_flags_with_measurements(self):
        flag1 = RepositoryFlagFactory(repository=self.repo, flag_name="flag1")
        flag2 = RepositoryFlagFactory(repository=self.repo, flag_name="flag2")
        MeasurementFactory(
            name="flag_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch=self.branch.name,
            flag_id=flag1.pk,
            commit_sha=self.commit.pk,
            timestamp="2022-06-21T00:00:00",
            value=75.0,
        )
        MeasurementFactory(
            name="flag_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch=self.branch.name,
            flag_id=flag1.pk,
            commit_sha=self.commit.pk,
            timestamp="2022-06-22T00:00:00",
            value=75.0,
        )
        MeasurementFactory(
            name="flag_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch=self.branch.name,
            flag_id=flag1.pk,
            commit_sha=self.commit.pk,
            timestamp="2022-06-22T01:00:00",
            value=85.0,
        )
        MeasurementFactory(
            name="flag_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch=self.branch.name,
            flag_id=flag2.pk,
            commit_sha=self.commit.pk,
            timestamp="2022-06-21T00:00:00",
            value=85.0,
        )
        MeasurementFactory(
            name="flag_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch=self.branch.name,
            flag_id=flag2.pk,
            commit_sha=self.commit.pk,
            timestamp="2022-06-22T00:00:00",
            value=95.0,
        )
        MeasurementFactory(
            name="flag_coverage",
            owner_id=self.org.pk,
            repo_id=self.repo.pk,
            branch=self.branch.name,
            flag_id=flag2.pk,
            commit_sha=self.commit.pk,
            timestamp="2022-06-22T01:00:00",
            value=85.0,
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
            "before": timezone.now().isoformat(),
        }
        data = self.gql_request(query_flags, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "flags": {
                            "edges": [
                                {
                                    "node": {
                                        "name": "flag1",
                                        "percentCovered": 80.0,
                                        "measurements": [
                                            {
                                                "timestamp": "2022-06-21T00:00:00+00:00",
                                                "avg": 75.0,
                                                "min": 75.0,
                                                "max": 75.0,
                                            },
                                            {
                                                "timestamp": "2022-06-22T00:00:00+00:00",
                                                "avg": 80.0,
                                                "min": 75.0,
                                                "max": 85.0,
                                            },
                                        ],
                                    }
                                },
                                {
                                    "node": {
                                        "name": "flag2",
                                        "percentCovered": 90.0,
                                        "measurements": [
                                            {
                                                "timestamp": "2022-06-21T00:00:00+00:00",
                                                "avg": 85.0,
                                                "min": 85.0,
                                                "max": 85.0,
                                            },
                                            {
                                                "timestamp": "2022-06-22T00:00:00+00:00",
                                                "avg": 90.0,
                                                "min": 85.0,
                                                "max": 95.0,
                                            },
                                        ],
                                    }
                                },
                            ]
                        }
                    }
                }
            }
        }

    def test_fetch_flags_without_measurements(self):
        query = """
            query Flags(
                $org: String!
                $repo: String!
                $branch: String!
            ) {
                owner(username: $org) {
                    repository(name: $repo) {
                        branch(name: $branch) {
                            flags {
                                edges {
                                    node {
                                        name
                                        percentCovered
                                    }
                                }
                            }
                        }
                    }
                }
            }
        """
        RepositoryFlagFactory(repository=self.repo, flag_name="flag1")
        RepositoryFlagFactory(repository=self.repo, flag_name="flag2")
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "branch": self.branch.name,
        }
        data = self.gql_request(query, variables=variables)
        assert data == {
            "owner": {
                "repository": {
                    "branch": {
                        "flags": {
                            "edges": [
                                {
                                    "node": {
                                        "name": "flag1",
                                        "percentCovered": None,
                                    }
                                },
                                {
                                    "node": {
                                        "name": "flag2",
                                        "percentCovered": None,
                                    }
                                },
                            ]
                        }
                    }
                }
            }
        }
