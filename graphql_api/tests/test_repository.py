from freezegun import freeze_time
import datetime

from django.test import TransactionTestCase
from ariadne import graphql_sync

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory
from .helper import GraphQLTestHelper, paginate_connection

query_repository = """{
    me {
        owner {
            repositories(first: 1) {
                edges {
                    node {
                        name
                        coverage
                        active
                        private
                        updatedAt
                        latestCommitAt
                    }
                }
            }
        }
    }
}
"""


class TestFetchRepository(GraphQLTestHelper, TransactionTestCase):
    def fetch_repository(self):
        data = self.gql_request(query_repository, user=self.user)
        return data["me"]["owner"]["repositories"]["edges"][0]["node"]

    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")

    @freeze_time("2021-01-01")
    def test_when_repository_has_no_coverage(self):
        RepositoryFactory(author=self.user, active=True, private=True, name="a")
        assert self.fetch_repository() == {
            "name": "a",
            "active": True,
            "private": True,
            "coverage": None,
            "latestCommitAt": None,
            "updatedAt": "2021-01-01T00:00:00+00:00",
        }

    @freeze_time("2021-01-01")
    def test_when_repository_has_coverage(self):
        RepositoryFactory(
            author=self.user,
            active=True,
            private=True,
            name="a",
            cache={"commit": {"totals": {"c": 75}}},
        )
        assert self.fetch_repository() == {
            "name": "a",
            "active": True,
            "latestCommitAt": None,
            "private": True,
            "coverage": 75,
            "updatedAt": "2021-01-01T00:00:00+00:00",
        }
