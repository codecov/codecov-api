import datetime
from unittest.mock import patch

import yaml
from ariadne import graphql_sync
from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import BranchFactory, CommitFactory, RepositoryFactory

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


class TestCommit(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov")
        self.repo = RepositoryFactory(author=self.org, name="gazebo", private=False)
        self.head = CommitFactory(repository=self.repo)
        self.commit = CommitFactory(repository=self.repo)
        self.branch = BranchFactory(
            repository=self.repo, head=self.commit.commitid, name="test1"
        )
        self.branch = BranchFactory(
            repository=self.repo, head=self.head.commitid, name="test2"
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
        variables = {
            "org": self.org.username,
            "repo": self.repo.name,
        }
        query = query_branches % (self.org.username, self.repo.name)
        data = self.gql_request(query, variables=variables)
        branches = data["owner"]["repository"]["branches"]["edges"]
        assert type(branches) == list
        assert any(branch["node"]["name"] == "master" for branch in branches)
        assert any(branch["node"]["name"] == "test1" for branch in branches)
        assert any(branch["node"]["name"] == "test2" for branch in branches)
        assert len(branches) == 3
