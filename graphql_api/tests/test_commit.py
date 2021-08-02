import yaml
import asyncio
import datetime
from unittest.mock import patch
from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, CommitFactory
from reports.tests.factories import (
    CommitReportFactory,
    ReportSessionFactory,
    ReportLevelTotalsFactory,
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
        query = query_commit % "message,createdAt,commitid,author { username }"
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
        session_one = ReportSessionFactory(report=self.report, provider="circleci")
        session_two = ReportSessionFactory(report=self.report, provider="travisci")
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

    @patch("core.commands.commit.commit.CommitCommands.get_final_yaml")
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
        f = asyncio.Future()
        f.set_result(fake_config)
        command_mock.return_value = f
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["yaml"] == yaml.dump(fake_config)

    @patch("core.commands.commit.commit.CommitCommands.get_file_content")
    @patch("core.commands.commit.commit.CommitCommands.get_file_coverage")
    def test_fetch_commit_coverage_file_call_the_command(
        self, coverage_mock, content_mock
    ):
        query = (
            query_commit
            % 'coverageFile(path: "path") { content,coverage { line,coverage } }'
        )
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
            "path": "path",
        }
        fake_coverage = {
            "content": "file content",
            "coverage": [{"line": 0, "coverage": 0}],
        }
        f = asyncio.Future()
        f.set_result("file content")
        content_mock.return_value = f
        coverage_mock.return_value = [{"coverage": 0, "line": 0}]
        data = self.gql_request(query, variables=variables)
        coverageFile = data["owner"]["repository"]["commit"]["coverageFile"]
        assert coverageFile["content"] == fake_coverage["content"]
        assert coverageFile["coverage"] == fake_coverage["coverage"]

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
        f = asyncio.Future()
        f.set_result(fake_compare)
        command_mock.return_value = f
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["compareWithParent"] == fake_compare

    @patch("compare.commands.compare.compare.CompareCommands.get_impacted_files")
    def test_impacted_files_comparison_call_the_command(self, command_mock):
        query = query_commit % "compareWithParent { impactedFiles { path } }"
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
            "commit": self.commit.commitid,
        }
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        fake_compare = [
            {
                "path": "src/config.js",
            },
        ]
        f = asyncio.Future()
        f.set_result(fake_compare)
        command_mock.return_value = f
        data = self.gql_request(query, variables=variables)
        commit = data["owner"]["repository"]["commit"]
        assert commit["compareWithParent"]["impactedFiles"][0] == {
            "path": "src/config.js"
        }
