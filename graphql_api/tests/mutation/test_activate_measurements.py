from unittest.mock import patch

from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: ActivateMeasurementsInput!) {
  activateMeasurements(input: $input) {
    error {
      __typename
    }
  }
}
"""


class ActivateMeasurementsTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory()

    def test_when_unauthenticated(self):
        data = self.gql_request(
            query,
            variables={
                "input": {
                    "owner": "codecov",
                    "repoName": "test-repo",
                    "measurementType": "FLAG_COVERAGE",
                }
            },
        )
        assert (
            data["activateMeasurements"]["error"]["__typename"]
            == "UnauthenticatedError"
        )

    @patch(
        "core.commands.repository.interactors.activate_measurements.ActivateMeasurementsInteractor.execute"
    )
    def test_when_authenticated(self, execute):
        data = self.gql_request(
            query,
            owner=self.owner,
            variables={
                "input": {
                    "owner": "codecov",
                    "repoName": "test-repo",
                    "measurementType": "FLAG_COVERAGE",
                }
            },
        )
        assert data == {"activateMeasurements": None}
