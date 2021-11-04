import asyncio
from unittest.mock import patch

import pytest
from asgiref.sync import sync_to_async
from django.test import TransactionTestCase

from codecov_auth.tests.factories import OwnerFactory
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
        self.user = OwnerFactory(username="codecov-user")
        asyncio.set_event_loop(asyncio.new_event_loop())

    @patch("codecov_auth.commands.owner.owner.OwnerCommands.set_yaml_on_owner")
    def test_mutation_dispatch_to_command(self, command_mock):
        # mock the command to return a Future which resolved to the owner
        f = asyncio.Future()
        f.set_result(self.user)
        command_mock.return_value = f
        input = {
            "username": self.user.username,
            "yaml": "codecov:\n  require_ci_to_pass: true",
        }
        data = self.gql_request(query, user=self.user, variables={"input": input})
        command_mock.assert_called_once_with(input["username"], input["yaml"])
        data["setYamlOnOwner"]["owner"]["username"] == self.user.username
