from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from codecov_auth.models import Session
from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: CreateApiTokenInput!) {
  createApiToken(input: $input) {
    error {
      __typename
    }
    fullToken
    session {
      ip
      lastseen
      lastFour
      type
      name
      useragent
    }
  }
}
"""


class CreateApiTokenTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")

    def test_when_unauthenticated(self):
        data = self.gql_request(query, variables={"input": {"name": "yo"}})
        assert data["createApiToken"]["error"]["__typename"] == "UnauthenticatedError"

    def test_when_authenticated(self):
        name = "yo"
        data = self.gql_request(
            query, owner=self.owner, variables={"input": {"name": name}}
        )
        created_token = self.owner.session_set.filter(name=name).first()
        assert data["createApiToken"]["session"] == {
            "name": name,
            "ip": None,
            "lastseen": None,
            "useragent": None,
            "type": Session.SessionType.API.value,
            "lastFour": str(created_token.token)[-4:],
        }

    def test_when_authenticated_full_token(self):
        name = "yo"
        data = self.gql_request(
            query, owner=self.owner, variables={"input": {"name": name}}
        )
        created_token = self.owner.session_set.filter(name=name).first()
        assert data["createApiToken"]["fullToken"] == str(created_token.token)
