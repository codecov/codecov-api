from unittest.mock import patch

from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: CreateStripeSetupIntentInput!) {
  createStripeSetupIntent(input: $input) {
    error {
      __typename
    }
    clientSecret
  }
}
"""


class CreateStripeSetupIntentTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")

    def test_when_unauthenticated(self):
        data = self.gql_request(query, variables={"input": {"owner": "somename"}})
        assert (
            data["createStripeSetupIntent"]["error"]["__typename"]
            == "UnauthenticatedError"
        )

    def test_when_unauthorized(self):
        other_owner = OwnerFactory(username="other-user")
        data = self.gql_request(
            query,
            owner=self.owner,
            variables={"input": {"owner": other_owner.username}},
        )
        assert (
            data["createStripeSetupIntent"]["error"]["__typename"]
            == "UnauthorizedError"
        )

    @patch("services.billing.stripe.SetupIntent.create")
    def test_when_validation_error(self, setup_intent_create_mock):
        setup_intent_create_mock.side_effect = Exception("Some error")
        data = self.gql_request(
            query, owner=self.owner, variables={"input": {"owner": self.owner.username}}
        )
        assert (
            data["createStripeSetupIntent"]["error"]["__typename"] == "ValidationError"
        )

    def test_when_owner_not_found(self):
        data = self.gql_request(
            query, owner=self.owner, variables={"input": {"owner": "nonexistent-user"}}
        )
        assert (
            data["createStripeSetupIntent"]["error"]["__typename"] == "ValidationError"
        )

    @patch("services.billing.stripe.SetupIntent.create")
    def test_success(self, setup_intent_create_mock):
        setup_intent_create_mock.return_value = {"client_secret": "test-client-secret"}
        data = self.gql_request(
            query, owner=self.owner, variables={"input": {"owner": self.owner.username}}
        )
        assert data["createStripeSetupIntent"]["clientSecret"] == "test-client-secret"
