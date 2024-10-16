from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from graphql_api.tests.helper import GraphQLTestHelper

query = """
    mutation($input: StartTrialInput!) {
        startTrial(input: $input) {
            error {
                __typename
                ... on ResolverError {
                    message
                }
            }
        }
    }
"""


class StartTrialMutationTest(GraphQLTestHelper, TransactionTestCase):
    def _request(self, owner=None, org_username: str = None):
        return self.gql_request(
            query,
            variables={"input": {"orgUsername": org_username}},
            owner=owner,
        )

    def test_unauthenticated(self):
        assert self._request() == {
            "startTrial": {
                "error": {
                    "__typename": "UnauthenticatedError",
                    "message": "You are not authenticated",
                }
            }
        }

    def test_authenticated(self):
        owner = OwnerFactory()
        owner.save()
        assert self._request(owner=owner, org_username=owner.username) == {
            "startTrial": None
        }
