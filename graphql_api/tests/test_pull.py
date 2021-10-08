from freezegun import freeze_time

from django.test import TransactionTestCase

from core.models import Pull
from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, PullFactory, CommitFactory
from .helper import GraphQLTestHelper


query_repository = """{
    me {
        owner {
            repository(name: "test-repo-for-pull") {
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
        return data["me"]["owner"]["repository"]["pulls"]["edges"][0]["node"]

    @freeze_time("2021-02-02")
    def setUp(self):
        self.user = OwnerFactory(username="test-pull-user", name="boii")
        self.repository = RepositoryFactory(author=self.user, active=True, private=True, name="test-repo-for-pull")
        self.pull = PullFactory(
            repository=self.repository,
            title="test-pull-request",
            author=self.user,
            head=CommitFactory(repository=self.repository, author=self.user, commitid="5672734ij1n234918231290j12nasdfioasud0f9").commitid,
            base=None,
        )

    def test_when_repository_has_null_base(self):
        assert self.fetch_repository() == {
            'title': None,
            'state': 'OPEN',
            'pullId': 1,
            'updatestamp': None,
            'author': {
                'username': 'test-pull-user'
            },
            'head': {
                'commitid': '5672734ij1n234918231290j12nasdfioasud0f9'
            },
            'base': None
        }