from django.test import TransactionTestCase
from shared.encryption.yaml_secret import yaml_secret_encryptor

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory

from .helper import GraphQLTestHelper


class TestEncodedString(TransactionTestCase, GraphQLTestHelper):
    def _request(self, variables=None):
        query = f"""
            query EncodedSecretString($value: String!) {{
                owner(username: "{self.org.username}") {{
                    repository(name: "{self.repo.name}") {{
                        ... on Repository {{
                            encodedSecretString(value: $value) {{
                                value
                            }}
                        }}
                    }}
                }}
            }}
        """
        data = self.gql_request(query, owner=self.owner, variables=variables)
        return data["owner"]["repository"]["encodedSecretString"]["value"]

    def setUp(self):
        self.org = OwnerFactory(username="test-org")
        self.repo = RepositoryFactory(
            name="test-repo",
            author=self.org,
            private=True,
        )
        self.owner = OwnerFactory(permission=[self.repo.pk])

    def test_encoded_secret_string(self):
        res = self._request(variables={"value": "token-1"})
        check_encryptor = yaml_secret_encryptor
        assert "token-1" in check_encryptor.decode(res[7:])
