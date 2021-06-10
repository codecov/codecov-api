import datetime

from django.test import TransactionTestCase
from ariadne import graphql_sync

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, CommitFactory
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
        self.org = OwnerFactory(username="codecov")
        self.repo = RepositoryFactory(author=self.org, name="gazebo", private=False)
        self.author = OwnerFactory()
        self.commit = CommitFactory(repository=self.repo)

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
