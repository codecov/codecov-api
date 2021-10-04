from freezegun import freeze_time

from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, PullFactory
from .helper import GraphQLTestHelper

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

query_repository_with_pull = """{
    me {
        owner {
            repository(name: "test-repo") {
                name
                pulls {
                    edges {
                        node {
                            title
                            state
                            pullId
                            updatestamp
                        }
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

    def fetch_repository_with_pulls(self):
        data = self.gql_request(query_repository_with_pull, user=self.user)
        return data["me"]["owner"]["repository"]["pulls"]["edges"][0]["node"]

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

    @freeze_time("2021-01-01")
    def test_when_repository_has_pull_request(self):
        repo = RepositoryFactory(author=self.user, active=True, private=True, name="test-repo")
        PullFactory(pullid=10, repository_id=repo.repoid, title="test-pull-request")
        assert self.fetch_repository_with_pulls() == {
            'title': 'test-pull-request',
            'state': 'open',
            'pullId': 10,
            'updatestamp': '2021-01-01T00:00:00'
        }