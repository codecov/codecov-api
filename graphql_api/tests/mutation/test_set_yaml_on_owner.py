from django.test import TransactionTestCase
from unittest.mock import patch

from codecov_auth.models import Session
from codecov_auth.tests.factories import OwnerFactory
from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: SetYamlOnOwnerInput!) {
  setYamlOnOwner(input: $input) {
    error
    owner {
        username
    }
  }
}
"""


class SetYamlOnOwnerMutationTest(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.user = OwnerFactory(username="codecov-user")

    @patch("graphql_api.commands.owner.owner.OwnerCommands.set_yaml_on_owner")
    def test_mutation_dispatch_to_command(self, command_mock):
        input = {
            "username": self.user.username,
            "yaml": "codecov:\n  require_ci_to_pass: true",
        }
        self.gql_request(query, user=self.user, variables={"input": input})
        command_mock.assert_called_once_with(input["username"], input["yaml"])
