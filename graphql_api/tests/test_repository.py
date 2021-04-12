from freezegun import freeze_time
import datetime

from django.test import TestCase
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
                    }
                }
            }
        }
    }
}
"""

class TestFetchRepository(GraphQLTestHelper, TestCase):

    def fetch_repository(self):
        self.client.force_login(self.user)
        data = self.gql_request(query_repository)
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
            "updatedAt": '2021-01-01T00:00:00+00:00',
        }

    @freeze_time("2021-01-01")
    def test_when_repository_has_coverage(self):
        RepositoryFactory(
            author=self.user,
            active=True,
            private=True,
            name="a",
            cache={
                "commit": {
                    "totals": {
                        "c": 75
                    }
                }
            }
        )
        assert self.fetch_repository() == {
            "name": "a",
            "active": True,
            "private": True,
            "coverage": 75,
            "updatedAt": '2021-01-01T00:00:00+00:00',
        }
