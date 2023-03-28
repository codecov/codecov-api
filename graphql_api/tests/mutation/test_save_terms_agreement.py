from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from graphql_api.tests.helper import GraphQLTestHelper

query = """
    mutation($input: SaveTermsAgreementInput!) {
        saveTermsAgreement(input: $input) {
            error {
                __typename
                ... on ResolverError {
                    message
                }
            }
        }
    }
"""


class SaveSaveTermsAgreementMutationTest(GraphQLTestHelper, TransactionTestCase):
    def _request(self, user=None):
        return self.gql_request(
            query,
            variables={"input": {"termsAgreement": True}},
            user=user,
        )

    def test_unauthenticated(self):
        assert self._request() == {
            "saveTermsAgreement": {
                "error": {
                    "__typename": "UnauthenticatedError",
                    "message": "You are not authenticated",
                }
            }
        }

    def test_authenticated(self):
        owner = OwnerFactory()
        assert self._request(user=owner) == {"saveTermsAgreement": None}
