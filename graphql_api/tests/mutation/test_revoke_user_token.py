from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory, UserTokenFactory
from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: RevokeUserTokenInput!) {
  revokeUserToken(input: $input) {
    error {
      __typename
    }
  }
}
"""


class RevokeUserTokenTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")

    def test_unauthenticated(self):
        data = self.gql_request(query, variables={"input": {"tokenid": "testing"}})
        assert data["revokeUserToken"]["error"]["__typename"] == "UnauthenticatedError"

    def test_authenticated(self):
        user_token = UserTokenFactory(owner=self.owner)
        tokenid = str(user_token.external_id)
        data = self.gql_request(
            query, owner=self.owner, variables={"input": {"tokenid": tokenid}}
        )
        assert data["revokeUserToken"] is None
        deleted_user_token = self.owner.user_tokens.filter(external_id=tokenid).first()
        assert deleted_user_token is None
