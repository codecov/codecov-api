from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: UpdateProfileInput!) {
  updateProfile(input: $input) {
    error {
      __typename
    }
    me {
      email
      user {
        name
      }
    }
  }
}
"""


class UpdateProfileTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")

    def test_when_unauthenticated(self):
        data = self.gql_request(query, variables={"input": {"name": "yo"}})
        assert data["updateProfile"]["error"]["__typename"] == "UnauthenticatedError"

    def test_when_authenticated(self):
        name = "yo"
        data = self.gql_request(
            query, owner=self.owner, variables={"input": {"name": name}}
        )
        assert data["updateProfile"]["me"]["user"]["name"] == name
