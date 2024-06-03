from django.test import TransactionTestCase, override_settings

from codecov_auth.tests.factories import OwnerFactory
from core.tests.factories import BranchFactory, RepositoryFactory
from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: RegenerateRepositoryUploadTokenInput!) {
  regenerateRepositoryUploadToken(input: $input) {
    error {
      __typename
      ... on ResolverError {
        message
      }
    }
  }
}
"""

repo_query = """{
    me {
      owner {
        repository(name: "gazebo") {
          ... on Repository {
            uploadToken
          }
        }
      }
    }
  }
"""


class RegenerateRepositoryUploadTokenTests(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov")
        self.repo = RepositoryFactory(author=self.org, name="gazebo", active=True)
        self.old_repo_token = self.repo.upload_token

    def test_when_authenticated_update_token(self):
        user = OwnerFactory(
            organizations=[self.org.ownerid], permission=[self.repo.repoid]
        )

        data = self.gql_request(
            query,
            owner=user,
            variables={"input": {"repoName": "gazebo", "owner": "codecov"}},
        )

        repo_result = self.gql_request(
            repo_query,
            owner=self.org,
        )

        assert (
            repo_result["me"]["owner"]["repository"]["uploadToken"]
            != self.old_repo_token
        )
        assert data == {"regenerateRepositoryUploadToken": None}

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
