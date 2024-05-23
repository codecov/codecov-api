from unittest.mock import PropertyMock, patch

from django.test import TransactionTestCase, override_settings

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import RepositoryFactory, RepositoryTokenFactory
from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: EraseRepositoryInput!) {
  eraseRepository(input: $input) {
    error {
      __typename
      ... on ResolverError {
        message
      }
    }
  }
}
"""


class EraseRepositoryTests(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov", service="github")
        self.repo = RepositoryFactory(author=self.org, name="gazebo", active=True)

    def test_when_authenticated(self):
        data = self.gql_request(
            query,
            owner=self.org,
            variables={
                "input": {
                    "repoName": "gazebo",
                }
            },
        )

        assert data == {"eraseRepository": None}

    def test_when_unauthenticated(self):
        data = self.gql_request(
            query,
            owner=None,
            variables={
                "input": {
                    "repoName": "gazebo",
                }
            },
        )
        assert data["eraseRepository"]["error"]["__typename"] == "UnauthenticatedErrsor"

    def test_when_validation_error_repo_not_found(self):
        data = self.gql_request(
            query,
            owner=self.org,
            variables={
                "input": {
                    "repoName": "DNE",
                }
            },
        )
        assert data["eraseRepository"]["error"]["__typename"] == "ValidationError"

    @override_settings(IS_ENTERPRISE=True)
    @patch("services.self_hosted.is_admin_owner")
    def test_when_not_self_hosted_admin(self, is_admin_owner):
        is_admin_owner.return_value = False
        data = self.gql_request(
            query,
            owner=self.org,
            variables={
                "input": {
                    "repoName": "gazebo",
                }
            },
        )

        assert data["eraseRepository"]["error"]["__typename"] == "UnauthorizedError"

    @override_settings(IS_ENTERPRISE=True)
    @patch("services.self_hosted.is_admin_owner")
    def test_when_self_hosted_admin(self, is_admin_owner):
        is_admin_owner.return_value = True

        data = self.gql_request(
            query,
            owner=self.org,
            variables={
                "input": {
                    "repoName": "gazebo",
                }
            },
        )

        assert data == {"eraseRepository": None}
