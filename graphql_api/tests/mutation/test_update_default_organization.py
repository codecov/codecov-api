from django.test import TransactionTestCase

from codecov_auth.models import OwnerProfile
from codecov_auth.tests.factories import OwnerFactory
from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: UpdateDefaultOrganizationInput!) {
  updateDefaultOrganization(input: $input) {
    error {
      __typename
    }
  }
}
"""


class UpdateProfileTestCase(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.default_organization_username = "sample-default-org-username"
        self.default_organization = OwnerFactory(
            username=self.default_organization_username, service="github"
        )
        self.user = OwnerFactory(
            username="sample-owner",
            service="github",
            organizations=[self.default_organization.ownerid],
        )

    def test_when_authenticated(self):
        self.gql_request(
            query,
            user=self.user,
            variables={"input": {"username": self.default_organization_username}},
        )
        owner_profile: OwnerProfile = OwnerProfile.objects.filter(
            owner_id=self.user.ownerid
        ).first()
        assert owner_profile.default_org == self.default_organization
