from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

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


class SaveTermsAgreementMutationTest(GraphQLTestHelper, TransactionTestCase):
    def _request(self, owner=None):
        return self.gql_request(
            query,
            variables={
                "input": {
                    "termsAgreement": True,
                    "businessEmail": "something@email.com",
                    "name": "codecov-user",
                }
            },
            owner=owner,
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
        assert self._request(owner=owner) == {"saveTermsAgreement": None}
