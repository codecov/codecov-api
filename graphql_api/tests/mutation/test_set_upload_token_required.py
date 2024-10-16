from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory

from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: SetUploadTokenRequiredInput!) {
  setUploadTokenRequired(input: $input) {
    error {
      __typename
      ... on ResolverError {
        message
      }
    }
  }
}
"""


class SetUploadTokenRequiredTests(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov")

    def test_when_authenticated_updates_upload_token_required(self):
        user = OwnerFactory(
            organizations=[self.org.ownerid],
        )
        self.org.admins = [user.ownerid]
        self.org.save()

        data = self.gql_request(
            query,
            owner=user,
            variables={
                "input": {"orgUsername": "codecov", "uploadTokenRequired": True}
            },
        )

        assert data["setUploadTokenRequired"] is None

    def test_when_validation_error_org_not_found(self):
        data = self.gql_request(
            query,
            owner=self.org,
            variables={
                "input": {
                    "orgUsername": "non_existent_org",
                    "uploadTokenRequired": True,
                }
            },
        )
        assert (
            data["setUploadTokenRequired"]["error"]["__typename"] == "ValidationError"
        )

    def test_when_unauthorized_non_admin(self):
        non_admin_user = OwnerFactory(
            organizations=[self.org.ownerid],
        )

        data = self.gql_request(
            query,
            owner=non_admin_user,
            variables={
                "input": {"orgUsername": "codecov", "uploadTokenRequired": True}
            },
        )

        assert (
            data["setUploadTokenRequired"]["error"]["__typename"] == "UnauthorizedError"
        )

    def test_when_unauthenticated(self):
        data = self.gql_request(
            query,
            variables={
                "input": {"orgUsername": "codecov", "uploadTokenRequired": True}
            },
        )

        assert (
            data["setUploadTokenRequired"]["error"]["__typename"]
            == "UnauthenticatedError"
        )

    def test_when_not_part_of_org(self):
        non_part_of_org_user = OwnerFactory(
            organizations=[self.org.ownerid],
        )

        data = self.gql_request(
            query,
            owner=non_part_of_org_user,
            variables={
                "input": {"orgUsername": "codecov", "uploadTokenRequired": True}
            },
        )

        assert (
            data["setUploadTokenRequired"]["error"]["__typename"] == "UnauthorizedError"
        )
