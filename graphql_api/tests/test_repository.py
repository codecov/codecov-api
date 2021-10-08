from freezegun import freeze_time

from django.test import TransactionTestCase

from core.models import Pull
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, PullFactory, CommitFactory
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
                            author {
                                username
                            }
                            head {
                                commitid
                            }
                            base {
                                commitid
                            }
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
    def test_when_repository_has_null_base(self):
        self.repository = RepositoryFactory(author=self.user, active=True, private=True, name="test-repo")
        self.pull = PullFactory(
            pullid=40,
            repository=self.repository,
            title="test-pull-request",
            author=self.user,
            head=CommitFactory(repository=self.repository, author=self.user, commitid="5672734ij1n234918231290j12nasdfioasud0f9").commitid,
            base=None,
        )
        Pull.objects.filter(id=1).delete()
        assert self.fetch_repository_with_pulls() == {
            'title': 'test-pull-request',
            'state': 'open',
            'pullId': 40,
            'updatestamp': '2021-01-01T00:00:00',
            'author': {
                'username': 'codecov-user'
            },
            'head': {
                'commitid': '5672734ij1n234918231290j12nasdfioasud0f9'
            },
            'base': None
        }