from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: SetTokensRequiredInput!) {
  setTokensRequired(input: $input) {
    tokensRequired
    error {
      __typename
      ... on ResolverError {
        message
      }
    }
  }
}
"""


class SetTokensRequiredTests(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov")

    def test_when_authenticated_updates_tokens_required(self):
        user = OwnerFactory(
            organizations=[self.org.ownerid],
            permission=[self.org.ownerid],
            is_admin=True,
        )

        data = self.gql_request(
            query,
            owner=user,
            variables={"input": {"org_username": "codecov", "tokensRequired": True}},
        )

        assert data["setTokensRequired"]["tokensRequired"] == True

    def test_when_validation_error_org_not_found(self):
        data = self.gql_request(
            query,
            owner=self.org,
            variables={
                "input": {
                    "org_username": "non_existent_org",
                    "tokensRequired": True,
                }
            },
        )
        assert data["setTokensRequired"]["error"]["__typename"] == "ValidationError"

    def test_when_unauthorized_non_admin(self):
        non_admin_user = OwnerFactory(
            organizations=[self.org.ownerid],
            permission=[self.org.ownerid],
            is_admin=False,
        )

        data = self.gql_request(
            query,
            owner=non_admin_user,
            variables={"input": {"org_username": "codecov", "tokensRequired": True}},
        )

        assert data["setTokensRequired"]["error"]["__typename"] == "UnauthorizedError"

    def test_when_unauthenticated(self):
        data = self.gql_request(
            query,
            variables={"input": {"org_username": "codecov", "tokensRequired": True}},
        )

        assert (
            data["setTokensRequired"]["error"]["__typename"] == "UnauthenticatedError"
        )

    def test_when_not_part_of_org(self):
        non_part_of_org_user = OwnerFactory(
            organizations=[self.org.ownerid],
            permission=[self.org.ownerid],
            is_admin=False,
        )

        data = self.gql_request(
            query,
            owner=non_part_of_org_user,
            variables={"input": {"org_username": "codecov", "tokensRequired": True}},
        )

        assert data["setTokensRequired"]["error"]["__typename"] == "UnauthorizedError"
