from unittest.mock import patch

from django.test import TransactionTestCase, override_settings
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory

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
        self.non_admin_user = OwnerFactory(organizations=[self.org.ownerid])
        self.admin_user = OwnerFactory(organizations=[self.org.ownerid])
        self.org.add_admin(self.admin_user)

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

    def test_when_unauthenticated(self):
        data = self.gql_request(
            query,
            variables={
                "input": {
                    "repoName": "DNE",
                }
            },
        )
        assert data["eraseRepository"]["error"]["__typename"] == "UnauthenticatedError"

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

    def test_when_other_admin(self):
        data = self.gql_request(
            query,
            owner=self.admin_user,
            variables={
                "input": {
                    "owner": "codecov",
                    "repoName": "gazebo",
                }
            },
        )

        assert data == {"eraseRepository": None}

    def test_when_not_other_admin(self):
        data = self.gql_request(
            query,
            owner=self.non_admin_user,
            variables={
                "input": {
                    "owner": "codecov",
                    "repoName": "gazebo",
                }
            },
        )

        assert data["eraseRepository"]["error"]["__typename"] == "UnauthorizedError"
