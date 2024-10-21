from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from codecov_auth.models import UserToken
from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: CreateUserTokenInput!) {
  createUserToken(input: $input) {
    error {
      __typename
    }
    fullToken
    token {
      id
      type
      name
      lastFour
    }
  }
}
"""


class CreateApiTokenTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")

    def test_unauthenticated(self):
        data = self.gql_request(query, variables={"input": {"name": "test"}})
        assert data["createUserToken"]["error"]["__typename"] == "UnauthenticatedError"

    def test_authenticated(self):
        name = "test"
        data = self.gql_request(
            query, owner=self.owner, variables={"input": {"name": name}}
        )
        user_token = self.owner.user_tokens.filter(name=name).first()
        assert user_token

        assert data["createUserToken"] == {
            "token": {
                "id": str(user_token.external_id),
                "name": name,
                "type": UserToken.TokenType.API.value,
                "lastFour": str(user_token.token)[-4:],
            },
            "fullToken": str(user_token.token),
            "error": None,
        }
