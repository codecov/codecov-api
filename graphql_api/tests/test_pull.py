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
        return data["me"]["owner"]["repository"]["pulls"]["edges"]

    def setUp(self):
        self.user = OwnerFactory(username="test-pull-user")
        self.repository = RepositoryFactory(author=self.user, active=True, private=True, name="test-repo-for-pull")

    @freeze_time("2021-02-02")
    def test_when_repository_has_null_base(self):
        PullFactory(
            repository=self.repository,
            pullid=18,
            title="test-null-base",
            author=self.user,
            head=CommitFactory(repository=self.repository, author=self.user, commitid="5672734ij1n234918231290j12nasdfioasud0f9").commitid,
            base=None,
        )
        assert self.fetch_repository()[1]["node"] == {
            'title': "test-null-base",
            'state': 'OPEN',
            'pullId': 18,
            'updatestamp': '2021-02-02T00:00:00',
            'author': {
                'username': 'test-pull-user'
            },
            'head': {
                'commitid': '5672734ij1n234918231290j12nasdfioasud0f9'
            },
            'base': None
        }

    @freeze_time("2021-02-02")
    def test_with_complete_pull_request(self):
        PullFactory(
            repository=self.repository,
            title="test-pull-request",
            pullid=13,
            author=self.user,
            head=CommitFactory(repository=self.repository, author=self.user, commitid="5672734ij1n234918231290j12nasdfioasud0f9").commitid,
            base=CommitFactory(repository=self.repository, author=self.user, commitid="9asd78fa7as8d8fa97s8d7fgagsd8fa9asd8f77s").commitid,
        )
        assert self.fetch_repository()[1]["node"] == {
            'title': 'test-pull-request',
            'state': 'OPEN',
            'pullId': 13,
            'updatestamp': '2021-02-02T00:00:00',
            'author': {
                'username': 'test-pull-user'
            },
            'head': {
                'commitid': '5672734ij1n234918231290j12nasdfioasud0f9'
            },
            'base': {
                'commitid': '9asd78fa7as8d8fa97s8d7fgagsd8fa9asd8f77s'
            }
        }
