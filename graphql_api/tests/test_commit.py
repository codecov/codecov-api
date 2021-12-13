import asyncio
import datetime
from unittest.mock import AsyncMock, patch

import yaml
from django.test import TransactionTestCase
from shared.reports.types import LineSession

from codecov_auth.tests.factories import OwnerFactory
from core.models import Commit
from core.tests.factories import CommitFactory, RepositoryFactory
from graphql_api.types.enums import UploadErrorEnum, UploadState
from reports.tests.factories import (
    CommitReportFactory,
    ReportLevelTotalsFactory,
    UploadErrorFactory,
    UploadFactory,
)

from .helper import GraphQLTestHelper, paginate_connection

query_commit = """
query FetchCommit($org: String!, $repo: String!, $commit: String!) {
  owner(username: $org) {
    repository(name: $repo) {
      commit(id: $commit) {
        %s
      }
    }
  }
}
"""

query_commits = """
query FetchCommits($org: String!, $repo: String!) {
  owner(username: $org) {
    repository(name: $repo) {
        commits {
            edges {
                node {
                    %s
                }
            }
        }
    }
  }
}
"""


class MockCoverage(object):
    def __init__(self, cov):
        self.coverage = cov
        self.sessions = [
            LineSession(0, None),
            LineSession(1, None),
            LineSession(2, None),
        ]


class MockLines(object):
    def __init__(self):
        self.lines = [
            [0, MockCoverage("1/2")],
            [1, MockCoverage(1)],
            [2, MockCoverage(0)],
        ]
        self.totals = MockCoverage(83)


class MockReport(object):
    def get(self, file):
        lines = MockLines()
        return MockLines()

    def filter(self, **kwargs):
        return self

    @property
    def flags(self):
        return {"flag_a": True, "flag_b": True}


class EmptyReport(MockReport):
    def get(self, file):
        return None


class TestCommit(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        self.org = OwnerFactory(username="codecov")
        self.repo = RepositoryFactory(author=self.org, name="gazebo", private=False)
        self.author = OwnerFactory()
        self.parent_commit = CommitFactory(repository=self.repo)
        self.commit = CommitFactory(
            repository=self.repo,
            totals={"c": "12", "diff": [0, 0, 0, 0, 0, "14"]},
            parent_commit_id=self.parent_commit.commitid,
        )
        self.report = CommitReportFactory(commit=self.commit)

    def test_fetch_commit(self):
        query = (
            query_commit
            % """
            message,
            createdAt,
            commitid,
            state,
            author { username }
        """
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["commitid"] == self.commit.commitid
        assert commit["message"] == self.commit.message
        assert commit["author"]["username"] == self.commit.author.username
        assert commit["state"] == self.commit.state

    def test_fetch_commits(self):
        query = query_commits % "message,commitid,ciPassed"
        self.repo_2 = RepositoryFactory(
            author=self.org, name="test-repo", private=False
        )
        commits_in_db = [
            CommitFactory(repository=self.repo_2, commitid=123),
            CommitFactory(repository=self.repo_2, commitid=456),
            CommitFactory(repository=self.repo_2, commitid=789),
        ]
        variables = {
            "org": self.org.username,
            "repo": self.repo_2.name,
        }
        data = self.gql_request(query, variables=variables)
        commits = paginate_connection(data["owner"]["repository"]["commits"])
        commits_commitid = [commit["commitid"] for commit in commits]
        assert sorted(commits_commitid) == ["123", "456", "789"]

    def test_fetch_parent_commit(self):
        query = query_commit % "parent { commitid } "
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["parent"]["commitid"] == self.parent_commit.commitid

    def test_resolve_commit_without_parent(self):
        self.commit_without_parent = CommitFactory(
            repository=self.repo, parent_commit_id=None
        )
        query = query_commit % "parent { commitid } "
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit_without_parent.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["parent"] == None

    def test_fetch_commit_coverage(self):
        ReportLevelTotalsFactory(report=self.report, coverage=12)
        query = query_commit % "totals { coverage } "
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["totals"]["coverage"] == 12

    def test_fetch_commit_build(self):
        session_one = UploadFactory(report=self.report, provider="circleci")
        session_two = UploadFactory(report=self.report, provider="travisci")
        query = query_commit % "uploads { edges { node { provider } } }"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        builds = paginate_connection(commit["uploads"])
        assert builds == [
            {"provider": session_one.provider},
            {"provider": session_two.provider},
        ]

    def test_fetch_commit_uploads_state(self):
        session_one = UploadFactory(
            report=self.report, provider="circleci", state=UploadState.PROCESSED.value
        )
        session_two = UploadFactory(
            report=self.report, provider="travisci", state=UploadState.ERROR.value
        )
        query = (
            query_commit
            % """
            uploads {
                edges {
                    node {
                        state
                    }
                }
            }
        """
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        uploads = paginate_connection(commit["uploads"])

        assert uploads == [
            {"state": UploadState.PROCESSED.name},
            {"state": UploadState.ERROR.name},
        ]

    def test_fetch_commit_uploads_errors(self):
        session = UploadFactory(
            report=self.report, provider="circleci", state=UploadState.ERROR.value
        )
        error_one = UploadErrorFactory(
            report_session=session, error_code=UploadErrorEnum.REPORT_EXPIRED.value
        )
        error_two = UploadErrorFactory(
            report_session=session, error_code=UploadErrorEnum.FILE_NOT_IN_STORAGE.value
        )

        query = (
            query_commit
            % """
            uploads {
                edges {
                    node {
                        errors {
                            edges {
                                node {
                                    errorCode
                                }
                            }
                        }
                    }
                }
            }
        """
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        [upload] = paginate_connection(commit["uploads"])
        errors = paginate_connection(upload["errors"])

        print(
            [
                {"errorCode": UploadErrorEnum.REPORT_EXPIRED.name},
                {"errorCode": UploadErrorEnum.FILE_NOT_IN_STORAGE.name},
            ]
        )

        assert errors == [
            {"errorCode": UploadErrorEnum.REPORT_EXPIRED.name},
            {"errorCode": UploadErrorEnum.FILE_NOT_IN_STORAGE.name},
        ]

    @patch(
        "core.commands.commit.commit.CommitCommands.get_final_yaml",
        new_callable=AsyncMock,
    )
    def test_fetch_commit_yaml_call_the_command(self, command_mock):
        query = query_commit % "yaml"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        fake_config = {"codecov": "yes"}
        command_mock.return_value = fake_config
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["yaml"] == yaml.dump(fake_config)

    @patch("core.commands.commit.commit.CommitCommands.get_file_content")
    @patch("core.models.ReportService.build_report_from_commit")
    def test_fetch_commit_coverage_file_call_the_command(
        self, report_mock, content_mock
    ):
        query = (
            query_commit
            % 'coverageFile(path: "path") { content,coverage { line,coverage }, totals {coverage} }'
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
            "path": "path",
        }
        fake_coverage = {
            "content": "file content",
            "coverage": [
                {"line": 0, "coverage": "P"},
                {"line": 1, "coverage": "H"},
                {"line": 2, "coverage": "M"},
            ],
            "totals": {"coverage": 83.0},
        }
        content_mock.return_value = "file content"

        report_mock.return_value = MockReport()
        data = self.gql_request(query, variables=variables)
        coverageFile = data["owner"]["repository"]["commit"]["coverageFile"]
        assert coverageFile["content"] == fake_coverage["content"]
        assert coverageFile["coverage"] == fake_coverage["coverage"]
        assert coverageFile["totals"] == fake_coverage["totals"]

    @patch("core.commands.commit.commit.CommitCommands.get_file_content")
    @patch("core.models.ReportService.build_report_from_commit")
    def test_fetch_commit_with_no_coverage_data(self, report_mock, content_mock):
        query = (
            query_commit
            % 'coverageFile(path: "path") { content,coverage { line,coverage }, totals {coverage} }'
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
            "path": "path",
        }
        fake_coverage = {
            "content": "file content",
            "coverage": [],
            "totals": None,
        }
        content_mock.return_value = "file content"

        report_mock.return_value = EmptyReport()
        data = self.gql_request(query, variables=variables)
        coverageFile = data["owner"]["repository"]["commit"]["coverageFile"]
        assert coverageFile["content"] == fake_coverage["content"]
        assert coverageFile["coverage"] == fake_coverage["coverage"]
        assert coverageFile["totals"] == fake_coverage["totals"]

    @patch("core.models.ReportService.build_report_from_commit")
    def test_flag_names(self, report_mock):
        query = query_commit % "flagNames"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
            "path": "path",
        }
        report_mock.return_value = MockReport()
        data = self.gql_request(query, variables=variables)
        flags = data["owner"]["repository"]["commit"]["flagNames"]
        assert flags == ["flag_a", "flag_b"]

    @patch(
        "compare.commands.compare.compare.CompareCommands.compare_commit_with_parent"
    )
    def test_fetch_commit_compare_call_the_command(self, command_mock):
        query = query_commit % "compareWithParent { state }"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        fake_compare = {"state": "PENDING"}
        command_mock.return_value = fake_compare
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["compareWithParent"] == fake_compare

    @patch("compare.commands.compare.compare.CompareCommands.get_impacted_files")
    def test_impacted_files_comparison_call_the_command(self, command_mock):
        query = query_commit % "compareWithParent { impactedFiles { headName } }"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        fake_compare = [
            {"head_name": "src/config.js",},
        ]
        command_mock.return_value = fake_compare
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["compareWithParent"]["impactedFiles"][0] == {
            "headName": "src/config.js"
        }

    @patch("compare.commands.compare.compare.CompareCommands.change_with_parent")
    def test_change_with_parent_call_the_command(self, command_mock):
        query = query_commit % "compareWithParent { changeWithParent }"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        fake_compare = 56.89
        command_mock.return_value = fake_compare
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["compareWithParent"]["changeWithParent"] == 56.89
