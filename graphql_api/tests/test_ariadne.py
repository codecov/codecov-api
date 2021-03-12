from django.test import TestCase
from ariadne import graphql_sync

from codecov_auth.tests.factories import OwnerFactory
from .helper import GraphQLTestHelper

class ArianeTestCase(GraphQLTestHelper, TestCase):

    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")

    def test_when_unauthenticated(self):
        query = "{ me { user { username }} }"
        data = self.gql_request('/graphql/gh/ariadne', query)
        assert data == {'me': None }

    def test_when_authenticated(self):
        self.client.force_login(self.user)
        query = "{ me { user { username avatarUrl }} }"
        data = self.gql_request('/graphql/gh/ariadne', query)
        assert data == {
            'me': {
                'user': {
                    'username': self.user.username,
                    'avatarUrl': self.user.avatar_url
                }
            }
        }
