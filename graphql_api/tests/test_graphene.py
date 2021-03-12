from django.test import TestCase

from codecov_auth.tests.factories import OwnerFactory
from .helper import GraphQLTestHelper

class GrapheneTestCase(GraphQLTestHelper, TestCase):

    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")

    def test_when_unauthenticated(self):
        query = "{ me { user { username }} }"
        data = self.gql_request('/graphql/gh/graphene', query)
        assert data == {'me': None }

    def test_when_authenticated(self):
        self.client.force_login(self.user)
        query = "{ me { user { username }} }"
        data = self.gql_request('/graphql/gh/graphene', query)
        assert data == {
            'me': {
                'user': {
                    'username': self.user.username,
                }
            }
        }
