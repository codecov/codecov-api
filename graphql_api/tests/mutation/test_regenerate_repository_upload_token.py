from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import OwnerFactory, RepositoryFactory

from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: RegenerateRepositoryUploadTokenInput!) {
  regenerateRepositoryUploadToken(input: $input) {
    token
    error {
      __typename
      ... on ResolverError {
        message
      }
    }
  }
}
"""


class RegenerateRepositoryUploadTokenTests(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov")
        self.repo = RepositoryFactory(author=self.org, name="gazebo")
        self.old_repo_token = self.repo.upload_token

    def test_when_authenticated_updates_token(self):
        user = OwnerFactory(
            organizations=[self.org.ownerid], permission=[self.repo.repoid]
        )

        data = self.gql_request(
            query,
            owner=user,
            variables={"input": {"repoName": "gazebo", "owner": "codecov"}},
        )

        assert data["regenerateRepositoryUploadToken"]["token"] != self.old_repo_token

    def test_when_validation_error_repo_not_found(self):
        data = self.gql_request(
            query,
            owner=self.org,
            variables={
                "input": {
                    "repoName": "DNE",
                    "owner": "codecov",
                }
            },
        )
        assert (
            data["regenerateRepositoryUploadToken"]["error"]["__typename"]
            == "ValidationError"
        )
