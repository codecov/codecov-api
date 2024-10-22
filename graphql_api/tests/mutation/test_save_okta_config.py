from django.test import TransactionTestCase
from shared.django_apps.codecov_auth.tests.factories import AccountFactory, OwnerFactory

from codecov_auth.models import OktaSettings
from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: SaveOktaConfigInput!) {
  saveOktaConfig(input: $input) {
    error {
      __typename
    }
  }
}
"""


class SaveOktaConfigTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.current_user = OwnerFactory(username="codecov-user")
        self.owner = OwnerFactory(
            username="codecov-owner",
            admins=[self.current_user.ownerid],
            account=AccountFactory(),
        )

    def test_when_unauthenticated(self):
        data = self.gql_request(
            query,
            variables={
                "input": {
                    "clientId": "some-client-id",
                    "clientSecret": "some-client-secret",
                    "url": "https://okta.example.com",
                    "enabled": True,
                    "enforced": True,
                    "orgUsername": self.owner.username,
                }
            },
        )
        assert data["saveOktaConfig"]["error"]["__typename"] == "UnauthenticatedError"

    def test_when_authenticated(self):
        data = self.gql_request(
            query,
            owner=self.owner,
            variables={
                "input": {
                    "clientId": "some-client-id",
                    "clientSecret": "some-client-secret",
                    "url": "https://okta.example.com",
                    "enabled": True,
                    "enforced": True,
                    "orgUsername": self.owner.username,
                }
            },
        )
        assert OktaSettings.objects.filter(account=self.owner.account).exists()
        assert data["saveOktaConfig"] is None
