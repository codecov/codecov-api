from unittest.mock import patch

from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: ActivateFlagsMeasurementsInput!) {
  activateFlagsMeasurements(input: $input) {
    error {
      __typename
    }
  }
}
"""


class ActivateFlagsMeasurementsTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory()

    def test_when_unauthenticated(self):
        data = self.gql_request(
            query, variables={"input": {"owner": "codecov", "repoName": "test-repo"}}
        )
        assert (
            data["activateFlagsMeasurements"]["error"]["__typename"]
            == "UnauthenticatedError"
        )

    @patch(
        "core.commands.repository.interactors.activate_flags_measurements.ActivateFlagsMeasurementsInteractor.execute"
    )
    def test_when_authenticated(self, execute):
        data = self.gql_request(
            query,
            user=self.user,
            variables={"input": {"owner": "codecov", "repoName": "test-repo"}},
        )
        assert data == {"activateFlagsMeasurements": None}
