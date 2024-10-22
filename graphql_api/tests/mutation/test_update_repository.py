from django.test import TransactionTestCase
from shared.django_apps.core.tests.factories import (
    BranchFactory,
    OwnerFactory,
    RepositoryFactory,
)

from graphql_api.tests.helper import GraphQLTestHelper

query = """
mutation($input: UpdateRepositoryInput!) {
  updateRepository(input: $input) {
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
              activated
            defaultBranch
          }
        }
      }
    }
}
"""


class UpdateRepositoryTests(GraphQLTestHelper, TransactionTestCase):
    def setUp(self):
        self.org = OwnerFactory(username="codecov", service="github")
        self.repo = RepositoryFactory(author=self.org, name="gazebo", activated=False)

    def test_when_authenticated_update_activated(self):
        data = self.gql_request(
            query,
            owner=self.org,
            variables={"input": {"activated": True, "repoName": "gazebo"}},
        )

        repo_result = self.gql_request(
            repo_query,
            owner=self.org,
        )
        assert repo_result["me"]["owner"]["repository"]["activated"] == True

        assert data == {"updateRepository": None}

    def test_when_authenticated_update_branch(self):
        BranchFactory.create(name="some other branch", repository=self.repo)
        data = self.gql_request(
            query,
            owner=self.org,
            variables={"input": {"branch": "some other branch", "repoName": "gazebo"}},
        )

        repo_result = self.gql_request(
            repo_query,
            owner=self.org,
        )
        assert (
            repo_result["me"]["owner"]["repository"]["defaultBranch"]
            == "some other branch"
        )

        assert data == {"updateRepository": None}

    def test_when_authenticated_branch_does_not_exist(self):
        data = self.gql_request(
            query,
            owner=self.org,
            variables={"input": {"branch": "Dne", "repoName": "gazebo"}},
        )

        assert data["updateRepository"]["error"]["__typename"] == "ValidationError"

    def test_when_unauthenticated(self):
        data = self.gql_request(
            query,
            variables={
                "input": {
                    "repoName": "gazebo",
                }
            },
        )
        assert data["updateRepository"]["error"]["__typename"] == "UnauthenticatedError"

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
        assert data["updateRepository"]["error"]["__typename"] == "ValidationError"
