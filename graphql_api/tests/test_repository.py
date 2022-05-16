from django.test import TransactionTestCase
from freezegun import freeze_time

from codecov_auth.tests.factories import OwnerFactory
from core.commands import repository
from core.tests.factories import PullFactory, RepositoryFactory

from .helper import GraphQLTestHelper

query_repository = """
query Repository($name: String!){
    me {
        owner {
            repository(name: $name) {
                %s
            }
        }
    }
}
"""

default_fields = """
    name
    coverage
    active
    private
    updatedAt
    latestCommitAt
    uploadToken
    defaultBranch
    author { username }
"""


class TestFetchRepository(GraphQLTestHelper, TransactionTestCase):
    def fetch_repository(self, name, fields=None):
        data = self.gql_request(
            query_repository % (fields or default_fields),
            user=self.user,
            variables={"name": name},
        )
        return data["me"]["owner"]["repository"]

    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")

    @freeze_time("2021-01-01")
    def test_when_repository_has_no_coverage(self):

        repo = RepositoryFactory(author=self.user, active=True, private=True, name="a")
        assert self.fetch_repository(repo.name) == {
            "name": "a",
            "active": True,
            "private": True,
            "coverage": None,
            "latestCommitAt": None,
            "updatedAt": "2021-01-01T00:00:00+00:00",
            "uploadToken": repo.upload_token,
            "defaultBranch": "master",
            "author": {"username": "codecov-user"},
        }

    @freeze_time("2021-01-01")
    def test_when_repository_has_coverage(self):
        repo = RepositoryFactory(
            author=self.user,
            active=True,
            private=True,
            name="b",
            cache={"commit": {"totals": {"c": 75}}},
        )
        assert self.fetch_repository(repo.name) == {
            "name": "b",
            "active": True,
            "latestCommitAt": None,
            "private": True,
            "coverage": 75,
            "updatedAt": "2021-01-01T00:00:00+00:00",
            "uploadToken": repo.upload_token,
            "defaultBranch": "master",
            "author": {"username": "codecov-user"},
        }

    def test_repository_pulls(self):
        repo = RepositoryFactory(author=self.user, active=True, private=True, name="a")
        PullFactory(repository=repo, pullid=2)
        PullFactory(repository=repo, pullid=3)

        res = self.fetch_repository(repo.name, "pulls { edges { node { pullId } } }")
        assert res["pulls"]["edges"][0]["node"]["pullId"] == 3
        assert res["pulls"]["edges"][1]["node"]["pullId"] == 2
