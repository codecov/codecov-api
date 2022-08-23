from uuid import uuid4

from django.test import TransactionTestCase

from codecov_auth.tests.factories import OrganizationLevelTokenFactory, OwnerFactory
from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: RegenerateOrgUploadTokenInput!) {
  regenerateOrgUploadToken(input: $input) {
    orgUploadToken
    error {
      __typename
    }
  }
}
"""


class RegenerateOrgUploadToken(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(
            name="codecov", plan="users-enterprisem", service="github"
        )
        OrganizationLevelTokenFactory(owner=self.owner)

    def test_when_unauthenticated(self):
        data = self.gql_request(query, variables={"input": {"owner": "codecov"}})
        assert (
            data["regenerateOrgUploadToken"]["error"]["__typename"]
            == "UnauthenticatedError"
        )

    def test_when_validation(self):
        owner = OwnerFactory(plan="users-enterprisem")
        data = self.gql_request(
            query,
            user=owner,
            variables={"input": {"owner": "rula"}},
        )
        assert (
            data["regenerateOrgUploadToken"]["error"]["__typename"] == "ValidationError"
        )

    def test_when_authenticated_regenerate_token(self):
        data = self.gql_request(
            query,
            user=self.owner,
            variables={"input": {"owner": "codecov"}},
        )
        newToken = data["regenerateOrgUploadToken"]["orgUploadToken"]
        assert newToken
        assert newToken != "random"
