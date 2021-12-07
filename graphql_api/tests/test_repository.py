from django.test import TransactionTestCase
from freezegun import freeze_time

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory

from .helper import GraphQLTestHelper

query_repository = """
query Repository($name: String!){
    me {
        owner {
            repository(name: $name) {
                name
                coverage
                active
                private
                updatedAt
                latestCommitAt
                uploadToken
            }
        }
    }
}
"""


class TestFetchRepository(GraphQLTestHelper, TransactionTestCase):
    def fetch_repository(self, name):
        data = self.gql_request(
            query_repository, user=self.user, variables={"name": name}
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
        }
