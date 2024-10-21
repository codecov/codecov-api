import asyncio
from unittest.mock import patch

from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: SetYamlOnOwnerInput!) {
  setYamlOnOwner(input: $input) {
    error {
      __typename
    }
    owner {
        username
    }
  }
}
"""


class SetYamlOnOwnerMutationTest(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.owner = OwnerFactory(username="codecov-user")
        asyncio.set_event_loop(asyncio.new_event_loop())

    @patch("codecov_auth.commands.owner.owner.OwnerCommands.set_yaml_on_owner")
    def test_mutation_dispatch_to_command(self, command_mock):
        # mock the command to return a Future which resolved to the owner
        f = asyncio.Future()
        f.set_result(self.owner)
        command_mock.return_value = f
        input = {
            "username": self.owner.username,
            "yaml": "codecov:\n  require_ci_to_pass: true",
        }
        data = self.gql_request(query, owner=self.owner, variables={"input": input})
        command_mock.assert_called_once_with(input["username"], input["yaml"])
        assert data["setYamlOnOwner"]["owner"]["username"] == self.owner.username
