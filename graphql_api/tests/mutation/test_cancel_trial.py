from datetime import datetime, timedelta

from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from graphql_api.tests.helper import GraphQLTestHelper
from plan.constants import TrialStatus

query = """
    mutation($input: CancelTrialInput!) {
        cancelTrial(input: $input) {
            error {
                __typename
                ... on ResolverError {
                    message
                }
            }
        }
    }
"""


class CancelTrialMutationTest(GraphQLTestHelper, TransactionTestCase):
    def _request(self, owner=None, org_username: str = None):
        return self.gql_request(
            query,
            variables={"input": {"orgUsername": org_username}},
            owner=owner,
        )

    def test_unauthenticated(self):
        assert self._request() == {
            "cancelTrial": {
                "error": {
                    "__typename": "UnauthenticatedError",
                    "message": "You are not authenticated",
                }
            }
        }

    def test_authenticated(self):
        now = datetime.utcnow()
        trial_start_date = now
        trial_end_date = now + timedelta(days=3)
        # TODO: add trial status here in CODE-3605-add-trial-logic
        owner = OwnerFactory(
            trial_start_date=trial_start_date, trial_end_date=trial_end_date
        )
        owner.save()
        assert self._request(owner=owner, org_username=owner.username) == {
            "cancelTrial": None
        }
