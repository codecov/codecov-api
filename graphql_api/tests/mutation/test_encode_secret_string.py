from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory
from shared.encryption.yaml_secret import yaml_secret_encryptor

from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: EncodeSecretStringInput!) {
  encodeSecretString(input: $input) {
    value
    error {
      __typename
      ... on ResolverError {
        message
      }
    }
  }
}
"""


class TestEncodeSecretString(TransactionTestCase, GraphQLTestHelper):
    def _request(self):
        data = self.gql_request(
            query,
            owner=self.org,
            variables={"input": {"repoName": "test-repo", "value": "token-1"}},
        )
        return data["encodeSecretString"]["value"]

    def setUp(self):
        self.org = OwnerFactory(username="test-org")
        self.repo = RepositoryFactory(
            name="test-repo",
            author=self.org,
            private=True,
        )
        self.owner = OwnerFactory(permission=[self.repo.pk])

    def test_encoded_secret_string(self):
        res = self._request()
        check_encryptor = yaml_secret_encryptor
        assert "token-1" in check_encryptor.decode(res[7:])
